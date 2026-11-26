# `STRATA_ARENA_LOCK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU 用 expert arena のうち、GPU driver に登録されず pageable のまま残る host RAM を、プロセスの resident memory としてロックするかを選ぶ。CUDA/HIP 実装では、UMA モードで arena 全体が未登録になる場合、通常登録の一部が拒否された場合、または by-need 登録の穴がある場合に関係する。通常の全域登録が完了した arena の登録範囲には作用しない。ロックは `lock_resident` / `lock_resident_ranges` による Windows の working-set minimum + `VirtualLock`、または Windows 以外の `mlock` で行われる（`engine/src/core/pinned.cu:1056-1085,1134-1143,1160-1173,1213-1271`, `engine/src/platform/memory.cpp:25-59,62-102,164-183`）。

CUDA/HIP と SYCL に読み取り箇所があるが、コード上の適用条件は同じではない。SYCL は `engine/sycl/src/core/pinned.dp.cpp` の arena 実装を使い、CUDA/HIP の UMA 未登録分岐は持たない（`engine/sycl/src/core/pinned.dp.cpp:366-402,459-468,500-510,557-566`）。

## 値と判定

数値・真偽値として parse せず、文字列全体が厳密に `0` と一致するかで判定する。大文字小文字、空白、数値としての妥当性は検査しない。したがって空文字列、`00`、`0anything`、`false`、`true`、` 0` はすべて「ロックする」側である。文字列比較は CUDA/HIP の通常経路で `std::string(env) != "0"`、Linux HIP の KFD NOREG 経路では `arena_lock_wanted` が同じ完全一致規則を使う（`engine/src/core/pinned.cu:1076-1082,1135-1143,1163-1172,1253-1269`, `engine/include/strata/core/kfd_quiet.hpp:118-123`）。

| 経路 | unset | ロックする値の例 | ロックしない値の例 |
|---|---|---|---|
| CUDA/HIP: 未登録の arena、部分登録の残り、by-need 登録の穴 | 通常はロック。Linux HIP の KFD NOREG が有効な未登録 arena だけはロックしない | 空文字、`1`、`true`、`00`、`0anything`、` 0` | 厳密に `0` |
| SYCL: pin cap による登録の残り | ロック | 空文字、`1`、`true`、`00`、`0anything`、` 0` | 厳密に `0` |
| SYCL: cap なしの全域経路 | この変数を参照せず、分岐に入らない | 該当なし | 該当なし |

Linux HIP の KFD NOREG の既定では、未設定は「ロックしない」、明示した値は `0` のときだけ「ロックしない」。それ以外の CUDA/HIP 対象経路では未設定は「ロックする」。大きなページ (`PageBacking::LargePages`) の場合は値にかかわらずロック処理を飛ばす（`engine/src/core/pinned.cu:1059-1083,1135-1143,1163-1173,1253-1271`, `engine/include/strata/core/kfd_quiet.hpp:120-123`, `engine/sycl/src/core/pinned.dp.cpp:459-468,500-510,557-566`）。

## 有効になる条件

- **CUDA/HIP で arena を使うこと。** `--mmap-experts` はファイルから expert を読む経路、`--stream-experts` は host arena を持たない経路なので、この arena lock の読み取り経路には入らない（CUDA/HIP: `engine/src/program/generate.cpp:8621-8635,8871-8900`; SYCL: `engine/sycl/src/program/generate.cpp:4711-4758`）。
- **ロック対象の未登録メモリが残ること。** CUDA/HIP で全域登録が成功すれば、`STRATA_ARENA_LOCK` の値に関係なく登録範囲を lock しない。driver 登録の拒否・上限による部分登録後は残りを lock するが、厳密な `0` なら行わない（`engine/src/core/pinned.cu:1096-1143,1145-1173`）。by-need 登録では登録穴を lock 対象とする（`engine/src/core/pinned.cu:1213-1271`）。
- **UMA の未登録モード。** CUDA/HIP では `arena_no_register()` が true のとき全 arena が未登録となり、この変数の通常の全体 lock 判定に入る。明示された `STRATA_ARENA_PIN_GIB` は engine の既定フラグより優先し、`none` は未登録、空でない他の値（`0` を含む）は登録側になる（`engine/src/core/pinned.cu:611-620`, `engine/include/strata/core/kfd_quiet.hpp:111-115`）。engine が未登録を既定選択するのは統合 GPU の Windows gfx1151、または設定が有効な Linux gfx1103 である（`engine/src/core/arch_defaults.cpp:140-149`）。
- **Linux HIP の Radeon 780M 系 NOREG 既定。** KFD quiet の NOREG が有効な場合にのみ、このクラスの未登録 arena は未設定で lock を省く。`STRATA_KFD_QUIET` / `STRATA_KFD_QUIET_NOREG` のスイッチや `STRATA_UMA_REGISTER=1` が既定を変え、`STRATA_ARENA_PIN_GIB` の明示値も arena の登録モードを決める（`engine/src/program/generate.cpp:4337-4354`, `engine/include/strata/core/kfd_quiet.hpp:104-123`）。`STRATA_ARENA_LOCK` に `0` 以外を明示すると、NOREG 既定でも lock を要求する。
- **SYCL の適用は狭い。** pin cap により通常登録の残りを扱う分岐でのみ値を読む。cap なしの分岐は `e = 0` として全 bytes を登録済みと扱い、変数を参照しない。Windows の deferred registration では、登録に失敗して残りが生じた場合だけ `register_slices()` が値を読む（`engine/sycl/src/core/pinned.dp.cpp:380-402,459-468,500-510,530-566`）。
- `STRATA_DEFERRED_REGISTER` が Windows の deferred 経路を選ぶ場合、値の読み取りは arena 構築時ではなく、`register_slices()` が未登録の末尾を処理するときになる。同経路は cap なし・共有 arena なし等の条件にも制約される（`engine/src/core/expert_source.cpp:3434-3449,6742-6759`; `engine/src/core/pinned.cu:1295-1322`; `engine/sycl/src/core/expert_source.cpp:3434-3449`; `engine/sycl/src/core/pinned.dp.cpp:530-567`）。
- 上記の標準的な arena lock 呼び出しは大きなページを使うと省略される（CUDA/HIP: `engine/src/core/pinned.cu:1064-1067,1135-1140,1163-1167,1253-1257`; SYCL: `engine/sycl/src/core/pinned.dp.cpp:461-468,501-505,558-566`）。

## 実行時の詳細

通常の CUDA/HIP 経路では `PinnedArena` の構築中に arena が確保された後、登録方式に応じて `getenv` し、未登録全体・部分登録末尾・by-need の穴をロックするか決める。Windows の deferred 経路では、予約だけ行う構築時には読まず、後で `register_slices()` が登録できなかった末尾をロックするときに読む。SYCL の非 deferred 経路も構築中に cap 残部を扱うときだけ読む（`engine/src/core/pinned.cu:1030-1085,1134-1173,1177-1271,1274-1322`; `engine/sycl/src/core/pinned.dp.cpp:366-402,459-510,519-567`）。

`STRATA_ARENA_LOCK` 自体を `static` に保存する箇所はなく、各対象分岐で `getenv` の結果を使う。よってプロセス起動後でも、該当分岐が実行される前の環境変更は反映され得る。分岐を通過した後の変更は、既に行ったロックを遡って切り替えない。通常の arena 構築はモデル読込中に進み、Windows deferred では登録スレッドで後から評価される（`engine/src/core/pinned.cu:1059,1135,1163,1253,1312`; `engine/sycl/src/core/pinned.dp.cpp:460,500,557`; `engine/src/core/expert_source.cpp:3434-3449`）。

lock helper が失敗しても、それ自体は例外や engine 終了にせず `LockResult.note` と `locked_bytes` を返す。Linux/macOS 等の POSIX 経路では `mlock` 失敗時に `mlock failed (raise ulimit -l)`、Windows では working-set API または `VirtualLock` の失敗位置を note にする（`engine/src/platform/memory.cpp:25-59,62-102,164-183`）。

## ログと測定値

通常の generate 経路は arena の note を stderr に `strata generate: expert arena: %s\n` と出す。note には `mlock` / `locked ... via working-set minimum + VirtualLock`、lock 失敗の文言、または無効化時の `arena lock disabled (STRATA_ARENA_LOCK=0); ` が含まれることがある。全域登録が成功した場合はこの変数の値を示す専用ログはない（CUDA/HIP: `engine/src/program/generate.cpp:8934-8937`; SYCL: `engine/sycl/src/program/generate.cpp:4780-4785`; note 生成: `engine/src/core/pinned.cu:1064-1084,1071,1081,1253-1269`; `engine/sycl/src/core/pinned.dp.cpp:500-510`）。

Linux HIP NOREG の未設定時は lock も無効化 note も出さない。`STRATA_TRACE` が設定されていて NOREG を選んだときは、別途 `strata trace: kfd quiet: expert arena not registered with the driver, no mlock (%s)\n` が stderr に出る（`engine/src/core/pinned.cu:1060-1072`; `engine/src/program/generate.cpp:4352-4354`）。

Strata の資料・ソースコメントに、この変数単独の再現可能な測定値は見つからなかったため、速度やメモリ量の効果は記載しない。

## 根拠

- 全ての実装読み取り箇所: `engine/src/core/pinned.cu:1059,1135,1163,1253,1312`; `engine/sycl/src/core/pinned.dp.cpp:460,500,557`。名前だけのコメント・設定 registry・テスト参照は実装の読み取りとは区別した。
- 値判定と Linux HIP NOREG 既定: `engine/include/strata/core/kfd_quiet.hpp:118-123`; `engine/src/core/pinned.cu:1059-1083`。
- arena 登録状態の決定: `engine/src/core/pinned.cu:611-629`; `engine/src/core/arch_defaults.cpp:140-149`; `engine/src/program/generate.cpp:4326-4354`。
- lock と失敗時 note: `engine/src/platform/memory.cpp:25-59,62-102,164-183`。
- SYCL 固有の cap 経路: `engine/sycl/src/core/pinned.dp.cpp:366-402,459-510,530-567`。
- CLI による arena 非使用経路と起動ログ: `engine/src/program/generate.cpp:8621-8635,8871-8900,8934-8937`; `engine/sycl/src/program/generate.cpp:4711-4758,4776-4785`。

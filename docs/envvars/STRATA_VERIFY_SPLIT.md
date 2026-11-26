# `STRATA_VERIFY_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の stepped 実行で、verify window の GPU graph を CPU expert の処理に合わせた追加の分割点でも区切るかを制御する。既定では追加分割を行う。OFF にすると、層グループの doorbell を処理する serve 境界は残しつつ、GPU の plan copy と VRAM expert group の後に設ける split 境界を作らない。これは graph の記録・実行スケジュールを変えるスイッチで、`record_window` 内の token 計算式そのものを切り替える分岐ではない（`engine/sycl/src/core/verify.cpp:2051-2082, 1642-1643, 1761-1774`）。

追加 split 境界があると、次の segment は plan（flag A）が pool から公開された時点で投入でき、CPU pool の仕事と GPU segment を重ねる経路を使える。実際に helper thread で重ねるのは `STRATA_VERIFY_PIPE` が未設定または先頭文字が `0` 以外の場合であり、`STRATA_VERIFY_PIPE=0` なら split 境界はあってもこの helper-thread 経路には入らない（`engine/sycl/src/core/verify.cpp:2493-2500, 2525-2557`）。

## 値と判定

`capture_segments` 内の関数ローカル `static const bool` が `std::getenv` の結果を一度読み、`e` が null であるか、先頭文字が `'0'` であるとき以外を ON と判定する。文字列全体の parse や数値検査はしない（`engine/sycl/src/core/verify.cpp:2076-2077`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `capture_segments` に入る SYCL verifier | ON | 空文字、`1`、`true`、`false`、` 0` など、先頭文字が `0` でない任意の文字列 | `0`、`0anything`、`0.1`、`00`（先頭文字が `0` の任意の文字列） |

したがって `false` や空白を含む値も ON になる。大小文字、数値としての妥当性、後続文字は判定されない。値の設定有無だけで判定する方式でもない。

## 有効になる条件

- Strata が SYCL verifier を使うビルド・実行経路であること。この読み取りは `engine/sycl/src/core/verify.cpp` にあり、今回の全参照検索では CUDA/HIP verifier に同名の読み取りは見つからなかった。
- `STRATA_VERIFY_STEPPED` が `env_on` で ON であること。`env_on` は未設定・空文字・先頭文字 `0` を OFF、それ以外を ON とする（`engine/sycl/src/core/verify.cpp:151-154, 192-194`）。
- verifier が all-resident 状態でないこと（`ar_on()` は `all_resident_ && !ar_off_`）。all-resident なら `capture()` は `capture_segments` を使わず、通常の graph capture に進む（`engine/sycl/include/strata/core/verify.hpp:370`, `engine/sycl/src/core/verify.cpp:2098-2105`）。
- `STRATA_VERIFY_EAGER` が未設定であること。設定されていれば（空文字でも）segmented capture を選ばず、eager replay 経路を使う（`engine/sycl/src/core/verify.cpp:2101-2105, 2479-2480, 2587-2590`）。
- stepped segmented execution で `--remote-expert-opt` を使わないこと。この組み合わせは split 値にかかわらず `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` で失敗する（`engine/sycl/src/core/verify.cpp:2493-2495`）。

## 実行時の詳細

`Verifier::run` は window を実行する前に `capture(T, err)` を呼ぶ。上記条件に合うと `capture_segments` が `step_hook_` を serve 境界に設定し、`STRATA_VERIFY_SPLIT` が ON の場合だけ `step_hook2_` を split 境界に設定してから `record_window` を記録する。`record_window` は `step_hook_` を各 group の doorbell 公開後に呼び、`step_hook2_` を host が計画を受けて GPU 側の VRAM expert group を処理した後に呼ぶ。この後者の境界は plan copy と VRAM group を含む segment を閉じ、CPU rows の処理中に次の GPU segment を準備できる位置である（`engine/sycl/src/core/verify.cpp:1642-1643, 1761-1774, 2058-2082`）。

未設定時は `split_on` が true なので追加境界が有効。先頭文字 `0` なら `step_hook2_` を設定せず、serve 境界だけで segment を記録する。`step_hook2_` の有無により `record_window` 内の lean graph 条件も変わり得るが、stepped capture 自体では step hook が存在し、`g_stepped` も true のため lean 条件は成立しない（`engine/sycl/src/core/verify.cpp:1026-1032, 2074-2079`）。

`split_on` は関数ローカル static のため、最初に `capture_segments` がこの初期化箇所へ到達した時点の値をプロセス内で保持する。window サイズごとの segment graph も `seg_[T]` が空でない場合には再記録しない。プロセス実行中に環境を書き換えても、初期化済み判定やキャプチャ済み graph には反映されない（`engine/sycl/src/core/verify.cpp:2051-2052, 2076, 2397`）。

## ログと測定値

この変数自身による ON/OFF ログや警告はない。別途 `STRATA_VERIFY_NODES` が設定されている場合は stderr に `strata verify: the %d-token window as %zu graph segments` を出し、記録された segment 数を確認できる。segment の graph 生成失敗は `verify: segment capture produced no graph`、記録処理が失敗した場合は `verify: segment capture: ...`、実行時に split 境界処理が失敗した場合は `verify: stepped split failed` という error 経路がある（`engine/sycl/src/core/verify.cpp:2061-2064, 2083-2090, 1772`）。この変数による性能・正確性の測定値は、参照した `docs/DETAILS.md` とソース内に見つからなかったため記載しない。

## 根拠

- `engine/sycl/src/core/verify.cpp:151-154, 192-194` — stepped mode の環境値判定。
- `engine/sycl/include/strata/core/verify.hpp:370, 400-411` — all-resident 判定と stepped segment / hook の説明。
- `engine/sycl/src/core/verify.cpp:1026-1032, 1642-1643, 1761-1774` — graph 条件、serve / split hook の呼び出し位置。
- `engine/sycl/src/core/verify.cpp:2051-2105, 2384-2398, 2476-2495, 2525-2557, 2575-2590` — segmented capture、cache、実行・失敗経路。
- `terminal/data/settings-register.json:51915` — settings register に名前があるが、runtime の値読み取り箇所ではない。

# `STRATA_ARENA_PIN_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

expert arena のホストメモリを GPU 用に登録する量と、登録しない UMA 経路を選びます。通常は arena 全体を登録しますが、非負の GiB 数を指定すると上限を設け、`none` は arena を登録しない経路を選びます。登録の上限は arena の割り当て量や GPU キャッシュ容量そのものではありません。CUDA/HIP 実装は `PinnedArena` 作成時に設定を読み、登録・分割登録・残り領域の resident lock を決めます（`engine/src/core/pinned.cu:611-629,1054-1098,1115-1143`）。

## 値と判定

読み取りは `std::getenv`。空文字と未設定は同じ扱いです。`none` と `auto` は小文字の文字列全体との完全一致で判定し、それ以外は `std::atoi` に渡します。したがって数値を厳密に検証せず、先頭の空白・符号・数字以降の文字は `atoi` の規則に従います（例: `12x` は 12、`x12` や `true` は 0）。負数の変換結果は `-1` に正規化されます。大文字の `NONE` / `AUTO` は特別値ではなく `atoi` 経由です（`engine/src/core/pinned.cu:623-630`; SYCL も同じ判定: `engine/sycl/src/core/pinned.dp.cpp:311-317`）。

| 条件 | unset / 空文字 | 設定値と効果 | 無効値・境界例 |
|---|---|---|---|
| 全 backend の共通判定 | `-1`（明示的な上限なし） | `0` は arena 全体を登録する設定。正の `N` は `N GiB` 上限 | 負数は上限なし。数値でない文字列は `atoi` により 0 となり全体登録扱い。数値後続の文字は無視される |
| CUDA/HIP の arena 登録モード | 明示的な「登録しない」指定ではない。エンジンの UMA no-register flag に従う | 完全一致の `none` は登録しない。数値（`0` を含む）や他の非空値は flag を上書きし、登録する側を選ぶ | `none `、`NONE` は `none` と一致しない。空文字は flag に戻る |
| Windows の CUDA/HIP sliced fallback | 通常の未指定上限。ByNeed arena では既定 29 GiB | `auto` は WDDM 共有メモリ予算から上限を計算。整数 `N>0` は明示上限、`0` は上限なし | ByNeed で `auto` の予算を算出できない場合は 29 GiB。通常 arena の `auto` は全体登録が拒否された後の sliced fallback にだけ使う |
| Windows 以外の sliced fallback | 上限なし | 整数 `N>0` は上限、`0` は上限なし | `auto` は Windows 用予算計算に入らず、実質上限なし |

整数上限は、呼び出し元が既に渡した `max_pinned_bytes` が正ならそちらが優先されます。上限は byte 数に換算され、arena 全体より小さいときに登録対象の prefix / ranges を途中で止めます（`engine/src/core/pinned.cu:1088-1098,1193-1205,1229-1238`）。

## 有効になる条件

- 設定が機能するには、expert arena を使う実行経路が必要です。変数は通常の CUDA/HIP engine と `engine/sycl` の arena 実装で読み取られます。設定を読む CLI parser はなく、CLI 引数に同名の優先規則はありません（`engine/src/core/pinned.cu:623-629`; `engine/sycl/src/core/pinned.dp.cpp:311-317`）。
- `max_pinned_bytes` が呼び出し元で既に指定されている場合、正の上限は環境値より優先されます。たとえば Windows/WSL2 の multi-GPU または remote expert 経路では、環境値が未設定なら engine 側の 8 GiB 制限が使われます。非負の環境値はその制限を置き換えます（`engine/src/program/generate.cpp:8748-8761`; SYCL: `engine/sycl/src/program/generate.cpp:4761-4775`）。
- Windows の通常 arena で正の上限が arena より小さい場合は最初から分割登録します。上限がない場合はまず全体登録を試し、失敗時に分割登録します。`auto` が予算計算に使われるのは後者です。共有 arena / remote experts / engine 側上限などで異なる登録経路に入る場合は、その caller 側制限が優先されます（`engine/src/core/pinned.cu:1088-1118`; `engine/src/core/expert_source.cpp:6742-6759`）。
- `STRATA_PIN_BY_NEED` が有効な Windows の経路では、GPU resident と推定された expert ranges を選んで登録します。ここでも `max_pinned_bytes` が先に適用され、そうでなければ正の環境値が上限です。`auto` はこの ByNeed 経路では使われません（`engine/src/core/pinned.cu:1192-1217`; `engine/src/program/generate.cpp:8773-8795`）。
- UMA の既定で登録しない経路でも、空でない設定はエンジンの flag より優先されます。特に `none` は登録しない、数値は登録する側です。Radeon 780M / Linux HIP の KFD NOREG 経路もこの優先規則を使います（`engine/src/core/pinned.cu:611-620`; `engine/include/strata/core/kfd_quiet.hpp:111-116`; `engine/src/program/generate.cpp:4326-4354`）。
- SYCL の `pinned.dp.cpp` は同じ文字列と上限判定を行いますが、arena 登録箇所では変換済み `cudaHostRegister` 呼び出しが `0` に置き換えられています。そのため、このソースからは CUDA/HIP と同じ実際の GPU 登録が行われるとは確認できません（`engine/sycl/src/core/pinned.dp.cpp:378-402`）。

## 実行時の詳細

`arena_pin_cap_gib()` と `arena_no_register()` は値を関数ローカルにキャッシュせず、呼び出しのたびに `getenv` を評価します。arena 構築中に上限判定と no-register 判定が別々に呼ばれるため、プロセス内で環境を変更した場合、後続の読み取りには反映されます（`engine/src/core/pinned.cu:611-630,1087-1098,1193-1215`）。

通常 arena は登録不要モードでなければ全体登録を試みます。全体が拒否された場合、layer 等の境界に沿って slice ごとに登録し、上限に達した位置または登録失敗で止まります。未登録部分は `STRATA_ARENA_LOCK` が `0` でない限り resident lock を試みます。登録失敗そのものはエラーを消費して arena を resident のまま続行する fallback で、note に `cudaHostRegister FAILED (...) - the arena is NOT pinned, so copies will be slow` を記録します（`engine/src/core/pinned.cu:1096-1147,1159-1172`）。

no-register 経路では GPU driver への登録を行わず、通常は arena 全体の resident lock を試みます。Linux HIP KFD NOREG が選んだ場合は既定で `mlock` を試さない扱いがありますが、`STRATA_ARENA_LOCK` が明示されていれば別途判定されます（`engine/src/core/pinned.cu:1054-1085`; `engine/include/strata/core/kfd_quiet.hpp:118-123`）。

エンジンの通常 arena の起動ログは `strata generate: expert arena: ...` に arena note を出します。明示的な非負値については、`strata generate: STRATA_ARENA_PIN_GIB=N: the whole expert arena is pinned`（0）または `...: the expert arena's pinning is capped`（正数）を stderr に出します。未設定で Windows/WSL2 multi-GPU / remote 経路が engine 上限を使うときは `strata generate: multi-GPU under WDDM: at most 8 GiB of the expert arena is pinned (STRATA_ARENA_PIN_GIB changes it)` です（`engine/src/program/generate.cpp:8753-8761`; SYCL: `engine/sycl/src/program/generate.cpp:4766-4774,4780-4785`）。

後段の必須 pinned staging allocation が失敗すると、Strata は `[pinned-memory-exhausted] the OS gave no more page-locked memory` を付け、arena の pinned 量が 2 GiB より大きければ「現在より 2 GiB 少なくする」`STRATA_ARENA_PIN_GIB=N` の再起動案内も付けます。SYCL の verify 経路では `verify: mapped staging allocation failed` を設定して失敗を返します（`engine/include/strata/core/pin_budget.hpp:212-218`; `engine/sycl/src/core/verify.cpp:708`）。

Strata host UI の `saferStart` は失敗ログに `pinned-memory-exhausted` または `mapped staging` が含まれ、かつ設定オブジェクトの `env.STRATA_ARENA_PIN_GIB` が falsy のとき、ログ内の数値ヒント、または RAM / 2 − 8 GiB（最低 4 GiB）、情報がなければ 16 GiB を環境設定へ加えて再起動を提案します。これは engine の `getenv` ではなく、ホスト側の再試行設定です（`app/host/server/native-resources.mjs:193-201`）。

## ログと測定値

`docs/DETAILS.md` は Windows の既定 29 GiB と pinned staging 失敗時の案内を記載しています（`docs/DETAILS.md:293-297`）。現行ソースでは 29 GiB は Windows ByNeed arena の未指定 / `auto` 予算取得失敗時の fallback であり、すべての Windows arena の一律既定ではありません（`engine/src/core/pinned.cu:1198-1206`）。ここでは性能値を追加しません。

## 根拠

- 読み取りと値変換: `engine/src/core/pinned.cu:611-630`, `engine/sycl/src/core/pinned.dp.cpp:311-317`
- arena 登録、上限、fallback: `engine/src/core/pinned.cu:1054-1147,1192-1238`; `engine/sycl/src/core/pinned.dp.cpp:378-417`
- caller 側上限、ログ、mode 選択: `engine/src/program/generate.cpp:4326-4354,8748-8761`; `engine/sycl/src/program/generate.cpp:4761-4785`
- ByNeed / helper 経路: `engine/src/core/expert_source.cpp:6742-6759`; `engine/include/strata/core/kfd_quiet.hpp:111-123`
- pinned staging の失敗とホスト再試行: `engine/include/strata/core/pin_budget.hpp:212-218`; `engine/sycl/src/core/verify.cpp:708`; `app/host/server/native-resources.mjs:193-201`

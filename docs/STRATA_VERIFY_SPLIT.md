# `STRATA_VERIFY_SPLIT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の段階実行で、GPU の VRAM expert group を処理した直後にも command graph の境界を設けるかを選びます。有効なら、その境界の次の segment を CPU expert の pool 処理と重ねて投入できるため、layer/group ごとの serve 境界に加えて、VRAM 側と CPU 側の処理を分ける地点ができます。無効にしても serve 境界は残ります。

この変数は `sycl/src/core/verify.cpp` のみで読み取られます。CUDA/HIP の verifier に同名変数の読み取りはありません。

## 値と判定

値全体や数値としての妥当性は検査せず、環境変数が未設定か、設定値の先頭文字が ASCII `0` かだけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（先頭文字は終端文字で、`'0'` ではない） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外（例: `1`, `true`, `false`, `abc`, 空白始まり） | 有効 |

大文字小文字、後続文字、整数変換は関係しません。`static const bool` に保存され、最初の段階 capture 時に評価されます。その後のプロセス内での環境変更は再評価されません。

## 有効になる条件

設定値が有効でも、次の経路でだけ追加境界が設定されます。

- SYCL verifier が `g_stepped`（`STRATA_VERIFY_STEPPED`）で段階実行を使う。
- 実行が通常の doorbell 経路（`!ar_on()`）で、`STRATA_VERIFY_EAGER` が未設定のため segment graph を capture する。

全 expert が VRAM にある `ar_on()` 経路では `capture_segments()` を通らず、この変数は読まれません。eager replay 経路でも segment capture を行わないため適用されません。`STRATA_VERIFY_STEPPED` 自体の判定は共通の `env_on()` によるもので、未設定・空文字・先頭文字 `0` は無効、それ以外は有効です。

段階実行で `--remote-expert-opt` を組み合わせると、実行側が `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` を返します。このエラーは `STRATA_VERIFY_SPLIT` の値にかかわらず、追加境界を無効にするだけでは回避されません。

## 実行時の詳細

`capture_segments()` は常に `step_hook_` を設定し、layer/group の doorbell publish 後に serve point を作ります。`STRATA_VERIFY_SPLIT` が有効なら `step_hook2_` も設定し、VRAM expert groups の後（CPU/PCIe share を待つ前）に split point を追加します。実行時、次 segment がこの split point の場合、`STRATA_VERIFY_PIPE` が有効なら pool 処理を helper thread で進め、GPU が flag A を受け取った時点で次 segment を投入します。これにより CPU 側の処理と GPU 側の segment が並行可能になります。`STRATA_VERIFY_PIPE` が無効なら pool 処理後に segment を進めます。

この変数が直接変更するのは graph の分割点です。record される演算自体は追加・削除されず、コードコメントも各 token の演算は変わらないとしています。実行開始時に `STRATA_VERIFY_NODES` が設定されていると、stderr に `strata verify: the %d-token window as %zu graph segments` の形式で segment 数を出します。segment capture に失敗した場合は capture error として返ります。

`docs/DETAILS.md` にはこの変数の説明や性能測定値を確認できませんでした。したがって性能効果や他 GPU での結果はここでは主張しません。

## 根拠

- `sycl/src/core/verify.cpp:92-104`: `env_on()` と `STRATA_VERIFY_STEPPED` の初期化。
- `sycl/src/core/verify.cpp:1687-1727`: segment capture、追加 hook、環境値判定、segment 数ログ。
- `sycl/src/core/verify.cpp:1463-1467`: VRAM group 後の split hook 呼び出しと、その後の flag B 待ち。
- `sycl/src/core/verify.cpp:2038-2045,2057-2065,2090-2124,2139-2147`: stepped run 条件、pool serve、split point での pipelined segment 投入。
- `sycl/include/strata/core/verify.hpp:358-369`: stepped mode と serve/split hook の説明、segment metadata。

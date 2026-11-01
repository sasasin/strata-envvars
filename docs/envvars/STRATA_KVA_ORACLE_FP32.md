# `STRATA_KVA_ORACLE_FP32`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリや GPU driver の環境変数動作は含めない。

## 役割

`STRATA_KVA_ORACLE` で指定した oracle capture ファイルを、fp32（4 byte float）として読むか bf16（2 byte 値）として読むかを選びます。既定は bf16 です。この変数だけでは KVA や oracle replay を有効化しません。KVA が実行され、設定モードが oracle になったときに限り、読み込むレコードの形式に影響します。

## 値と判定

共通 helper `kva_env_flag(name, false)` が `getenv()` の結果を判定します。値全体の parse や数値変換はせず、未設定または空文字なら既定値 `false`、それ以外は先頭文字が `'0'` でない場合に `true` です。したがって `1`, `true`, `false`, `2` は true、`0`, `0anything` は false です。空白・大文字小文字・後続文字は判定されません。

| 環境値 | `oracle_fp32` | 読込形式（oracle read が実行された場合） |
|---|---:|---|
| unset / 空文字 | false | bf16（2 byte） |
| 空でなく先頭が `0` | false | bf16（2 byte） |
| 空でなく先頭が `0` 以外 | true | fp32（4 byte） |

`STRATA_KVA_ORACLE` が未設定または空文字なら、この変数を helper に渡す分岐に入らず、`oracle_fp32` は構造体の既定値 false のままです。`STRATA_KVA_MODE=oracle` だけを指定し oracle directory を指定しない場合も同様です。CLI 引数によるこの値の上書きはありません。

## 有効になる条件

- `STRATA_KVA_ORACLE` が空でないと、設定読み取り時に本変数が評価され、oracle directory とともに `oracle_fp32` に保存されます。その後 `STRATA_KVA_MODE` が設定されていればモードを上書きします。値が `oracle` なら oracle mode、`linear` なら linear mode、それ以外（空を除く任意文字列を含む）なら identity mode です。よって oracle directory があっても、`STRATA_KVA_MODE=linear` 等では oracle file を読みません。
- 実際の oracle open は `kva_run` が true かつ mode が Oracle の場合だけです。KVA は `STRATA_KVA` が空でなく、先頭文字が `0` 以外で、当該 build に state-only 経路があり、実行が全層・単一の cold prompt であることなどを要します。Metal build には経路がありません。CUDA/HIP の state-only 経路が対象です。
- `kva_run` は capture mode、継続読み込み（`pos0 != 0`）、層分割、画像 prompt、DFlash2 tap、`STRATA_KVA_MIN_PROMPT` 未満の prompt、suffix により近似対象が残らない prompt では false です。既定 min prompt は 4096、既定 suffix は 2048 で、`n <= effective_suffix() + 64` も不適用です。
- 既定ではモデル形状が 48 layers / 512 experts でない場合も不適用です。`STRATA_KVA_ANY_MODEL` を設定するとこの形状制限を解除し、初回に stderr 警告を出します。generate 側では複数 GPU の layer split、`--batch`、`--peer-device` もプロセス全体を block します。これらは本変数の parse には影響せず、oracle replay が実行されない条件です。

## 実行時の詳細

本変数は `kva_config_from_env()` の中で、`STRATA_KVA_ORACLE` が非空の場合に限り `kva_env_flag("STRATA_KVA_ORACLE_FP32", false)` で読み取られます。通常実行では `kva_config()` がこの設定を function-local `static const` に一度だけ保存するため、初回評価後の環境変更は反映されません。テスト用 `kva_config_from_env()` は直接呼び出しのたびに再評価しますが、ここではテストの記述を本番動作の根拠にしていません。

oracle mode が実行可能になると、`Prefill::run_impl` は process-static `KvaTap` を oracle directory と `oracle_fp32` で初期化します。各近似対象 layer で `L<layer>.bin` を開き、fp32 指定時は 4 byte 単位で読み込みます。指定が false の場合は 2 byte 単位で読み、bf16 値を float に展開してから device residual に転送します。これは Strata がファイルを解釈・転送する処理の説明であり、ファイル生成側や外部ライブラリの挙動は含みません。

ファイルを開けない場合は `kva oracle: cannot read <path>`、seek 失敗は `kva oracle: cannot seek <path>`、必要数より短い場合は `kva oracle: short read of <path> at position …: wanted … values, got …`、転送失敗は `kva oracle: the upload failed` がエラーになります。layer 範囲外では `kva oracle: layer out of range` です。`run_impl` はこのエラーを返し、Prefill 呼び出し側は body failure として処理します。通常の KVA 状態ログは stderr に `strata prefill: KVA on: ... mode oracle` と出ます。不適用時に KVA が明示的に有効化されていれば `strata prefill: KVA configured but NOT applied: ...` と理由を出します。

## 根拠

- `include/strata/prefill/kva.hpp:69-93` — `oracle_fp32` の既定値と KVA 設定項目。
- `include/strata/prefill/kva.hpp:143-147,168-181,191-195` — flag 判定、oracle directory 条件、mode 上書き、プロセス内 cache。
- `include/strata/prefill/kva.hpp:43-49,104-133` — Metal backend の無効化と read の適用条件。
- `src/program/generate.cpp:6257-6279` — generate 初期化時の backend・batch・複数 GPU・peer device 条件と警告。
- `src/prefill/prefill.cpp:2947-2974` — `kva_run` 判定、oracle の初期化条件。
- `src/prefill/prefill.cpp:2890-2932,3689-3695` — oracle file の形式別読込、展開、device 転送、エラー。
- `src/prefill/prefill.cpp:5820-5856,7271-7279` — stderr の KVA 状態・不適用ログと Prefill error の伝播。
- `docs/KVA.md:108-128,169-189` — KVA 設定表、状態ログ例、capture/oracle の説明。詳細な測定値は本変数の読込形式を裏付けないため記載していない。

# `DS4_STORE_PUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の expert cache が VRAM から expert を追い出すとき、その expert のデータを RAM store に書き戻す機能を制御します。値が有効で、RAM store が利用可能な場合、VRAM にある追い出し対象の MXFP4 expert をホスト側へコピーし、store slot に登録します。CPU lane が後でその expert を使う際、元のモデルファイルを読む代わりに RAM store から利用できるようにする経路です。

## 値と判定

`env_tri()` は `std::getenv()` の値を `std::atoi()` に渡し、変数が未設定なら `-1`、設定されていて整数変換結果が 0 なら `0`、非 0 なら `1` を返します。変換前の文字列全体の検証はありません。

| `DS4_STORE_PUT` | `env_tri()` の結果 | 判定 |
|---|---:|---|
| 未設定 | -1 | `DS4_DEFAULTS` による既定値を使う |
| 空文字 | 0 | 無効 |
| `0`、`0abc`、整数に変換できない文字列 | 0 | 無効 |
| `1`、`2`、`-1`、`1abc` など、`atoi()` が非 0 を返す値 | 1 | 有効 |

`store_feature_default()` は明示値があれば 0 を無効、非 0 を有効とします。未設定なら `DS4_DEFAULTS` が `026` 系の既定値を選んだ場合は無効、それ以外では有効です。`defaults_026()` は `DS4_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致するかを初回評価時に static cache します。そのため、未設定時の `DS4_STORE_PUT` の既定動作は通常有効、`DS4_DEFAULTS` で 0.2.6 互換を選ぶと無効です。明示的な `DS4_STORE_PUT` はこの既定値に優先します。

根拠: `src/dsv41/ds4_model.cu:97-101`; `src/dsv41/ds4_experts_rule.hpp:16-27,203-208`。

## 有効になる条件

有効判定だけではコピーは行われません。expert swap の出力側で、次の条件がすべて成立する必要があります。

- DeepSeek V4.1 engine の expert cache が swap を処理している。
- RAM store (`store`) が初期化済みである。初期化には正の store 容量、非空の layer 群、MXFP4 形式、file-backed experts が必要です。容量は `--ssd-cache` または `DS4_STORE_GB` などで決まり、既定の自動容量が 0 になる場合もあります。
- swap の入力 expert の読み込み・VRAM へのコピーが成功している（`ok`）。
- layer が単一 member（`l.nm == 1`）である。
- layer の形式が MXFP4 である。
- `DS4_STORE_PUT` が有効である。

この環境変数の読み取りと分岐自体に、OS や backend、build macro による条件分岐はありません。対象処理は DeepSeek V4.1 engine の `ds4_model.cu` にあります。

RAM store の容量設定（`--ssd-cache`, `DS4_STORE_GB`）と `DS4_STORE_PUT` は別の制御です。容量は `--ssd-cache` が初期値ですが、`DS4_STORE_GB` が設定されるとその値で上書きされます（GGUF 以外では store 容量は 0）。自動容量が 0 になる場合も store は作られません。CLI に `DS4_STORE_PUT` と同じ意味の引数はありません。`--no-expert-cache` で expert cache を止めた場合も swap 経路がなくなります。

根拠: `src/dsv41/ds4_model.cu:3158,3184,5367-5382,5410-5413,7113-7116`; `src/dsv41/ds4_main.cpp:1325,1331`; `src/dsv41/ds4_model.hpp:37-44`。

## 実行時の詳細

値はモデル初期化時に一度読むのではなく、`swap_in_mx()` が上記条件を評価するたびに `env_tri("DS4_STORE_PUT")` で読みます。`DS4_STORE_PUT` の結果自体は static cache されません。一方 `DS4_DEFAULTS` は `defaults_026()` により初回呼び出し時の結果がプロセス内に cache されます。

条件成立後、`store->put_begin(layer, expert)` が未登録の expert 用 slot を確保します。既に store にある場合、または空き・置換可能 slot を確保できない場合は null を返し、その swap では書き込みを行いません。slot が得られた場合は、追い出し対象の VRAM slot から `l.blob` bytes を device-to-host の `cudaMemcpyAsync()` でコピーし、stream を同期して成否を確かめます。`put_done()` は成功時に slot を ready にし、失敗時に slot を解放します。

`DS4_STORE_PUT` が無効、store がない、layer が条件に合わない、または put slot が得られない場合は、この RAM store へのコピーを省略します。CPU lane は通常の file-backed 経路を使います。対象 swap の入力を VRAM へ移す処理自体が失敗した場合は stderr に `ds4 cache: layer %d expert %d: the move into VRAM failed` が出ます。put slot が取れない場合や put の device-to-host copy が失敗した場合には、この分岐に固有のログはありません。copy failure は `put_done(..., false)` により slot を解放します。

RAM store 自体が初期化できない場合は stderr に `ds4: --ssd-cache: the store could not start` が出ます。store が動作していると、実行統計には store hit/miss、slot 数、eviction 数、failed reads などが表示されますが、そこに put 成功数を個別表示する出力は確認できません。

根拠: `src/dsv41/ds4_model.cu:7083-7125,7148-7150`; `src/dsv41/ds4_store.hpp:259-304`; `src/dsv41/ds4_main.cpp:1589-1601`; `src/dsv41/ds4_model.cu:5485-5499`。

## 候補一覧との照合

`000_envvers.md` の候補は実装で実際に読み取られています。Strata の実行時読み取りは `src/dsv41/ds4_model.cu:7113` です。`apps/host/server/native-settings.mjs` と `strata_control/speed_switches.py` は DeepSeek speed-ups スイッチの値（`DS4_STORE_PUT=0` を含む）を設定ファイル用に書き出す設定であり、環境からこの変数を読む箇所ではありません（それぞれ `apps/host/server/native-settings.mjs:49-54`, `strata_control/speed_switches.py:48-55`）。テストとコメントの参照は実装の読み取り根拠には用いていません。

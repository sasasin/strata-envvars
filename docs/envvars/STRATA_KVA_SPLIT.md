# `STRATA_KVA_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

KVA（approximate late-layer state）で、近似処理または capture 対象にする最初の層番号を指定します。層番号は 0 始まりで、指定した層以降が対象です。値の設定だけでは KVA は有効にならず、別の `STRATA_KVA` と実行条件も満たす必要があります。既定値は 36 です。根拠: `include/strata/prefill/kva.hpp:54-57,85,157`。

## 値と判定

共通 helper は `std::getenv()` で値を取得し、未設定または空文字なら既定値を返し、それ以外は `std::atoll()` で整数に変換します。文字列全体の妥当性検査はありません。したがって数値の前後にある空白や符号は `atoll` の変換規則に従い、数字の後ろの文字列は値の判定に使われません。数字で始まらない非空文字列は変換結果 0 になります。根拠: `include/strata/prefill/kva.hpp:137-141,157`。

その後、実際に使う layer index は `max(split, 1)` を `min(..., n_layers)` で制限します。つまり 0、負値、数値に変換できない文字列は 1 層目からに補正され、`n_layers` より大きい値は `n_layers` に補正されます。48 層モデルで `48` 以上なら対象層がなく、通常の layer loop（0〜47）では近似対象がありません。1〜47 はその番号から最終層までが対象です。根拠: `src/prefill/prefill.cpp:2965,3614-3623`。

| 環境値 | 読み取り値 | 実効 split |
|---|---:|---:|
| 未設定 | 36 | `min(max(36, 1), n_layers)` |
| 空文字 | 36 | `min(max(36, 1), n_layers)` |
| `30` | 30 | `min(max(30, 1), n_layers)` |
| `0`、負値、非数値文字列 | 変換結果または整数値 | 1（負値・0・非数値は下限で補正） |
| `30tail` | `atoll` が読み取る数値接頭部の 30 | `min(30, n_layers)` |
| 層数を超える整数 | その整数 | `n_layers` |

`STRATA_KVA_SPLIT` 自体に CLI 引数や設定ファイルによる上書き経路は見つかりませんでした。実装が直接読むのは環境変数です。`STRATA_KVA` が KVA 全体の ON/OFF を決め、split の値はその機能が適用される場合にのみ実行位置へ反映されます。別の環境変数との値の優先順位や split の別設定経路はありません。根拠: `include/strata/prefill/kva.hpp:150-188`。

## 有効になる条件

- `STRATA_KVA` が設定され、空文字でなく、先頭文字が `0` 以外であること。KVA の既定は OFF です。`STRATA_KVA_SPLIT` が設定されていても、KVA が OFF なら近似処理には使われません。`STRATA_KVA` の判定根拠: `include/strata/prefill/kva.hpp:152-156`。
- Metal build では `kKvaBackend` が false となり、KVA は無効です。KVA 用の state-only path を持つ build は Metal 以外と定義されています。根拠: `include/strata/prefill/kva.hpp:43-49,156`。
- 一つの GPU、batch slots なし、peer device なしであること。層分割、`--batch`、`--peer-device` は engine 起動時に KVA 全体を block します。根拠: `src/program/generate.cpp:6257-6277`。
- prompt の読み取りが cold read（`pos0 == 0`）、画像なし、DFlash2 tap なし、全 trunk stage であること。prompt 長は `STRATA_KVA_MIN_PROMPT` 以上で、かつ実効 suffix より 64 token を超えて長い必要があります。根拠: `include/strata/prefill/kva.hpp:104-133`。
- 既定では測定された形状（48 層、512 experts）であること。形状が異なると適用されず、`STRATA_KVA_ANY_MODEL` が有効な場合だけ警告付きで許可されます。split の上限補正に使う層数は実際のモデル形状の `g.n_layers` です。根拠: `src/prefill/prefill.cpp:2953-2965`。

これらの条件を満たした prompt chunk のうち、suffix より前で終わる chunk だけが近似対象になります。対象 chunk で `l >= kva_split` の層が設定に従って state-only（既定）または `STRATA_KVA_SKIP=moe` の MoE skip 経路に入り、対象層の expert transfer も省かれます。`STRATA_KVA_ONLY` が `gdn` または `qsa` の場合は、その種別に合う層だけが対象です。根拠: `src/prefill/prefill.cpp:3115-3123,3382-3394,3619-3629`。

KVA capture が有効な場合、近似処理自体は `decline()` により行われませんが、capture 対象 layer の開始位置も `l >= kva_split` で決まります。根拠: `include/strata/prefill/kva.hpp:112-114`, `src/prefill/prefill.cpp:3621-3629`。

## 実行時の詳細

`kva_config_from_env()` は `STRATA_KVA_SPLIT` を `kva_env_i64()` に渡します。通常の engine 経路では `kva_config()` 内の function-local `static const KvaConfig` が最初の呼び出し時に作られ、その後の呼び出しは保存済み設定を使います。engine の KVA 条件確認で `kva_config()` が呼ばれ、prefill でも同じ設定が参照されます。したがってプロセス起動後に環境変数を変更しても、すでに初期化された設定には反映されません。根拠: `include/strata/prefill/kva.hpp:149-157,191-195`, `src/program/generate.cpp:6263-6265`, `src/prefill/prefill.cpp:2947-2955`。

CLI による split の上書きはありません。`STRATA_KVA_SPLIT` は初回設定読込時に一度読み取られます。実効値は prefill 時にモデル層数で clamp され、近似対象 layer 判定と capture layer 判定に使用されます。環境値そのものを変更するコードや子プロセスへ転送するコードは、対象名の全参照検索では見つかりませんでした。

prefill の stderr には、KVA が実行または capture されると `strata prefill: KVA ... split <値> ...` が出ます。この値は clamp 後の実効 split です。KVA が設定されているが適用されない場合にも、ログ条件を満たせば `KVA configured but NOT applied: ... split <値>` として実効 split が表示されます。KVA が未設定/OFFなら通常 KVA のログは出ません。根拠: `src/prefill/prefill.cpp:5820-5856`。

## 根拠

- 全参照を `rg -n --hidden --glob '!.git/**' 'STRATA_KVA_SPLIT'` で調査しました。実行コードでの読み取りは `include/strata/prefill/kva.hpp:157` の一箇所で、そこから同ファイルの `kva_env_i64()`（138-141 行）へ名前を渡しています。ほかの一致は設計文書の記述、コメント、テストコードでした。テストは値例を確認する手掛かりにとどめ、実行時挙動の根拠は本番コードに置いています。
- 既定 split 36 と 0 始まりの意味: `include/strata/prefill/kva.hpp:54-57,85`; 設定の変換: `include/strata/prefill/kva.hpp:137-157`; clamp と適用: `src/prefill/prefill.cpp:2965,3614-3629`。
- KVA の適用条件: `include/strata/prefill/kva.hpp:104-133`; process-wide block 条件: `src/program/generate.cpp:6257-6277`; 実行時ログ: `src/prefill/prefill.cpp:5820-5856`。
- 関連設計説明: `docs/KVA.md:10-14,43-58,106-128`。性能・品質測定値はこの文書の設定理由の説明に限られ、本調査で再測定していません。

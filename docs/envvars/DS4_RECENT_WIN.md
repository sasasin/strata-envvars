# `DS4_RECENT_WIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 v4.1 の expert cache にある「recent slots」について、CPU lane で使われた expert の使用履歴を何 tick 分保持して fill 候補を調べるかを指定します。最近の使用履歴に `DS4_RECENT_NEED` 回以上現れた未配置 expert が、空きまたは最も古い recent slot へのコピー候補になります。これは通常の expert cache の入れ替え基準ではなく、recent slots を有効にした経路の履歴窓です。

## 値と判定

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | `8.0f` を既定値として採用し、`int` に変換して 8 tick |
| 空文字 | `std::atof("")` が 0 を返し、整数化後に最小値 1 へ clamp |
| 数値文字列 | `std::atof` で `float` に変換し、`int` にキャストして小数部を落とした後、1 未満を 1 に clamp |
| 数値で始まる文字列（例 `12tail`） | `atof` が変換できる先頭の数値部分を使い、整数化してから clamp |
| 数値に変換できない文字列 | `atof` の 0 を整数化し、1 tick |
| 負値、または 1 未満の値 | 整数化後 `std::max(1, ...)` により 1 tick |

数値文字列全体の妥当性確認、警告、上限 clamp はありません。有限かつ `int` で表現可能な値についての規則です。範囲外値や NaN などの浮動小数点から整数への変換結果は、実装で検査されていません。

## 有効になる条件

- DS4 v4.1 のモデル実装（`src/dsv41/ds4_model.cu`）で読み取られます。この読み取り箇所自体に OS や build macro の分岐はありません。
- recent slots の数 `recent_n` が正である必要があります。初期値は `DS4_RECENT` 未設定時に 0 ですが、モデル読み込み時に、chunked prompt、GGUF、stream lane が有効で、lane 環境設定で無効化されていない場合は既定値 32 で再設定されます。`DS4_RECENT` を明示するとこの数を指定します。
- 層ごとの slot 設定では `--expert-cache` が有効（既定）で、expert が一部だけ VRAM に載る層（slot 数が 2 以上かつ expert 数未満）であることが必要です。recent slots の数を置いても、通常 VRAM 用に少なくとも 1 slot 残せる場合に限り、その層に recent slots が割り当てられます。`--no-expert-cache`、全 expert が VRAM に収まる層、slot 数不足、または `recent_n` が 0 の場合は `rc_n` が 0 となり、この環境変数が制御する履歴処理は行われません。
- OS/backend の既定経路について、実装コメントは one-GPU decode path の関連最適化を Linux・NVIDIA・単一の離散 GPU・helper GPU なしで既定有効とし、それ以外は旧経路と記しています。各設定を明示した場合はそれぞれの設定が判断するとあります。`DS4_RECENT_WIN` 自体に独立した OS/backend 判定はありません。

## 実行時の詳細

`env_f` は環境値が存在するかを確認し、設定されていれば `std::atof`、未設定なら渡された既定値を返す helper です。`recent_win` は model implementation の初期化時に通常のメンバー値として一度評価されます（static cache ではありません）。一方、環境値が再読込される仕組みはこの設定箇所にはなく、モデル作成後の環境変更は既に保持された `recent_win` に反映されません。

recent slots が設定された層では、各 cache tick の CPU lane expert 集合を layer ごとの `rc_hist` に追加し、deque の長さが `recent_win` を超える間、古い tick を削除します。その後、各 tick で CPU lane にいた expert のうち VRAM におらず、既に fill 中でもないものについて、履歴窓内に `DS4_RECENT_NEED` 回以上現れたものを fill 候補にします。`DS4_RECENT_FILLS` が 1 tick に開始する fill 数の上限を決め、候補のコピーが成功すると、次の tick の device table update を介して recent slot として扱われます。recent slot の設定数が 0 なら tick 処理は早期 return します。

この変数専用のログや不正値エラーはありません。`DS4_RECENT_STATS` が設定され、tick が発生していれば終了時に recent slots の tick 数・平均 tick 時間・fill 数などを stderr に出します。fill コピー失敗時は `ds4: recent-slot fill failed, slot left unmapped: ...`、prompt 前の drain が 5 秒を超えた場合は待たずに続行する旨の stderr ログがあります。これらは recent slots 全体の観測経路であり、`DS4_RECENT_WIN` の値を表示するログではありません。

## 根拠

- 値の取得 helper と `DS4_RECENT_WIN` の既定値・最小値 clamp: `src/dsv41/ds4_model.cu:1352,1577-1585`
- recent slots 数の初期値とモデル読み込み時の自動値: `src/dsv41/ds4_model.cu:1582-1585,2793-2800`
- one-GPU 経路の OS/backend 既定条件に関する実装コメント: `src/dsv41/ds4_model.cu:1369-1374`
- `--expert-cache` と層あたりの recent slot 割当条件: `src/dsv41/ds4_model.hpp:40`, `src/dsv41/ds4_main.cpp:2535`, `src/dsv41/ds4_model.cu:5553-5563`
- 履歴 deque の保持長、候補選択、履歴回数判定: `src/dsv41/ds4_model.cu:9112-9128`
- recent tick の早期 return: `src/dsv41/ds4_model.cu:9079-9083`
- 任意の終了統計ログ: `src/dsv41/ds4_model.cu:1924-1928`
- fill 失敗ログと prompt 前 drain timeout ログ: `src/dsv41/ds4_model.cu:8904-8924,9050-9077`

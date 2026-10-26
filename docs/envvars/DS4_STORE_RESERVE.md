# `DS4_STORE_RESERVE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 専用エンジンの RAM expert store で、GPU が読み取り用に可視化した expert slot のうち、GPU から回収して空ける slot 数の目標を指定します。値の単位は expert 数（slot 数）です。起動時の hot expert preload では同じ値に 64 を足した数の slot を空けておくため、初回 prompt のために preload する expert 数にも影響します。

これは Strata 全体や通常の `strata` エンジンの設定ではありません。専用ソース `src/dsv41/ds4_model.cu` が読む設定です。

## 値と判定

どちらの読み取り箇所も `std::getenv()` の有無で既定値を選び、設定値を `std::atoi()` で整数化します。文字列全体の検証、値域チェック、clamp はありません。

| 環境変数 | `cfg.reserve` に使う値 | 初期 preload が空ける値 (`leave`) |
|---|---:|---:|
| 未設定 | 192 | 256 |
| 設定あり | `(size_t) atoi(value)` | `(size_t) atoi(value) + 64` |

`atoi` のため、空文字や先頭が数値でない文字列は 0、`12tail` や `12.5` は 12 として扱われます。先頭の空白と符号も整数変換の対象です。たとえば `0` は `cfg.reserve=0`、`leave=64` です。

負値は許容値として定義されていません。変換後に `size_t` へキャストされるため、`cfg.reserve` は大きな符号なし値になります。一方、`leave` はその後 64 を加算し、符号なし整数の折り返しが起きます。たとえば `-1` なら `cfg.reserve` は最大値、`leave` は 63 です。コードに防止処理はなく、通常の正の slot 数以外を指定したときの利用可能性や結果は保証されません。

## 有効になる条件

変数が store を新たに有効化することはありません。`init_store()` が先に決める store 容量が正で、expert がファイルから読め、モデル先頭 layer の形式が MXFP4 のときに store が作られます。容量は `--ssd-cache` または `DS4_STORE_GB` と RAM の自動判定で決まり、容量が 0 以下などで `init_store()` が戻ると `DS4_STORE_RESERVE` の設定効果はありません。

runtime の `cfg.reserve` は GPU-mapped store の window 境界処理で使われます。`store_sync()` は `store->gpu_mapped()` が false の場合すぐ戻るため、GPU mapping がない構成では runtime に GPU 可視 slot を回収する処理は行われません。ただし、store が初期化され、profile に履歴があれば、`leave` による初期 preload 上限は GPU mapping の有無にかかわらず適用されます。

## 実行時の詳細

モデルのロード処理で `init_store()` が `cfg.reserve` を設定し、その直後に `preload_store()` が `leave` を計算します。profile の hit 数から expert を hot 順に並べ、`ExpertStore::preload()` は arena の最大 slot 数から `leave` を差し引いた分まで読み込みます。profile の hit 数がまだない場合は初期 preload を行いません。未設定なら、初期 preload は最大 slot 数から 256 slot を空けた範囲までです（候補の数が少なければ、その数まで）。

GPU-mapped store では各 window の `store_sync()` から `ExpertStore::sync()` が呼ばれます。ここでは GPU が読み取り中でない ready slot のうち、GPU に見せる slot を選んだ後、free slot が `cfg.reserve` 未満なら、score の低い GPU-visible slot を回収して目標数に近づけます。回収 slot は device table から外されます。これは常に設定値と同じ数だけ回収する動作ではなく、既に free の slot 数、visible slot の数、候補の score に依存します。

環境変数はモデル load 中に2回読み取られ、static cache には保存されません。load の完了後にプロセス環境を変更しても、この store の設定には反映されません。診断出力として、zero-copy 用のログには `cfg.reserve` が「slots kept evictable」として表示されます。

## 文書との照合

`docs/DEEPSEEK41.md` は RAM store が起動時にサイズを自動決定することと、`--ssd-cache` の指定を説明していますが、`DS4_STORE_RESERVE` の値や slot 回収規則は説明していません。ここではソース実装を根拠にしています。

## 根拠

- `src/dsv41/ds4_model.cu:2821-2823` — store 初期化と preload の順序。
- `src/dsv41/ds4_model.cu:4578-4611,4633-4636` — 自動コピー/store 容量の条件と store 初期化の早期 return。
- `src/dsv41/ds4_model.cu:4663-4664,4748-4782` — `cfg.reserve` と `leave` の変換、profile preload。
- `src/dsv41/ds4_model.cu:4800-4803` — GPU mapping がない場合の `store_sync()` の早期 return。
- `src/dsv41/ds4_store.hpp:69-70,286-329` — reserve の意味と GPU-visible slot の回収処理。
- `src/dsv41/ds4_store.hpp:220-237` — preload が arena の slot 数から `leave` を差し引いて読む処理。
- `src/dsv41/ds4_model.hpp:37-40` — RAM store と `--ssd-cache` の概要。
- `docs/DEEPSEEK41.md:48-53,97-104` — 利用者向けの RAM store 記述（環境変数個別の説明なし）。

# `DS4_STORE_THREADS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 (DS4) の RAM expert store が使うファイル読み取り worker の数を指定する。各 expert の gate / up / down の3つの領域読み取りが `IoQueue` に投入され、指定数の worker がそのキューを処理する。これは DS4 の store 初期化経路でのみ使われる変数で、通常のモデル読込全般のスレッド数を設定するものではない。

## 値と判定

値は `std::getenv()` で取得し、設定されていれば `std::atoi()` で整数に変換する。未設定時は `8`。空文字や数値として読めない文字列は `atoi` の結果が `0` となる。数値の後ろに文字が続く値は数値部分が変換される（例: `4x` は `4`）。したがって `4.5` は `4` になる。先頭空白や符号は `atoi` の変換規則に従う。

`ExpertStore::init()` は `IoQueue(std::max(1, c.threads))` を作るため、設定値が `0` または負数なら実際の worker は1本になる。正の値はその数の worker を作る。正数に対する上限 clamp はこのコードにはない。起動ログは clamp 前の `cfg.threads` を表示するため、値 `0` なら実際は1本で動作しても `0 reader threads` と表示される。

## 有効になる条件

この変数を読むのは `Ds4Model::init_store()` のみ。store の予算が正、layer が存在し、先頭 layer の形式が MXFP4 で、`file_experts` が有効な場合に `ExpertStore` の初期化へ進む。予算は `--ssd-cache` または `DS4_STORE_GB` などで決まり、store がこの条件で初期化されない場合は `DS4_STORE_THREADS` は読み取られず、効果もない。

## 実行時の詳細

値は `init_store()` が `ExpertStore::Cfg` を組み立てる際、モデル初期化中に一度読み取られる。以降の process environment の変更は既に作成された `IoQueue` の worker 数を変えない。

`ExpertStore::init()` は設定値を最低1に clamp して `IoQueue` を構築し、`IoQueue` の constructor はその数だけ worker thread を起動する。store の miss / prefetch は1 expert につき3件のファイル領域読み取りをキューへ入れる。worker は demand queue を先に処理し、低優先の prefetch queue は demand queue が空の時に処理する。このため値は読み取り処理の並列度を変えるが、どの expert を store に保持するかを決める値ではない。

store が正常に開始すると stderr に `ds4: RAM store: ... %d reader threads, ... reads` の形式で値が記録される。初期化に失敗した場合は `ds4: --ssd-cache: the store could not start` が出力される。

## 根拠

- `src/dsv41/ds4_model.cu:4633-4636,4657-4661` — store の初期化条件と、unset 時 `8`、設定時 `atoi` による `DS4_STORE_THREADS` の読取り。
- `src/dsv41/ds4_model.cu:4710-4723` — store の起動、失敗ログ、reader thread 数を含む起動ログ。
- `src/dsv41/ds4_store.hpp:73-108` — store の有効性検査後に `IoQueue` を `std::max(1, c.threads)` で生成。
- `src/dsv41/ds4_store.hpp:414-459` — 1 expert の3行列を3つの I/O job として投入。
- `src/dsv41/ds4_pool.hpp:132-168,180-225` — `IoQueue` が指定数の worker を起動し、キューから I/O job を処理する実装。
- `docs/DETAILS.md` と `docs/DEEPSEEK41.md` には、この変数の値や効果を説明する記述は見つからなかった。

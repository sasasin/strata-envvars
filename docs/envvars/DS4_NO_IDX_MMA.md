# `DS4_NO_IDX_MMA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek-V4.1 の indexer で、FP4 key のスコア計算に使う `ds4_index_score_mma`（simdgroup matrix を使う経路）を無効化し、通常の `ds4_index_score` に切り替えます。変数が未設定なら MMA 経路が既定です。名前に `NO` を含みますが、`DS4_NO_IDX_MMA` を設定すると MMA を止めます。

## 値と判定

数値や文字列の parse はなく、`std::getenv()` の戻り値が null かどうかだけを見ます。

| 環境変数の状態 | `idx_mma` | 該当する呼び出しでの選択 |
|---|---:|---|
| 未設定 | `true` | 条件を満たし MMA pipeline が使える場合は MMA、それ以外は通常の indexer |
| 空文字を含む何らかの値を設定 | `false` | 通常の `ds4_index_score` |

したがって `DS4_NO_IDX_MMA=0` も MMA を無効にし、`1` も同様です。値の長さ、先頭文字、数値としての範囲、大文字小文字は判定されません。CLI 引数や設定ファイルによる上書きはこの実装にはありません。

## 有効になる条件

- この読み取りは `STRATA_METAL` 定義下でビルドされる Metal 用 DeepSeek 経路にあります。Metal の CMake 構成は `strata_ds4` に `STRATA_METAL=1` を定義し、同じターゲットへ `ds4_finish.cpp` と `ds4_kernels.cu` を含めます（`metal/CMakeLists.txt:135-146,169`）。一般の CUDA/HIP/SYCL 経路ではこの環境変数を読む箇所は見つかりません。
- `index_score()` が呼ばれ、入力が `cand == nullptr` かつ `kfmt == 3`（FP4）であるときに MMA 経路を選べます。候補 index を使う呼び出し（`cand != nullptr`）や BF16 (`kfmt == 0`) は、この変数にかかわらず通常の indexer に進みます。
- MMA pipeline `ds4_index_score_mma` を取得できなければ、環境変数が未設定でも通常の indexer を実行します。
- DeepSeek モデルの prompt/decode の両方に `index_score()` 呼び出しがありますが、各呼び出しで上記の入力条件が適用されます。通常の `strata` の他モデルや indexer 以外の演算には影響しません。

## 実行時の詳細

`static const bool idx_mma` は `index_score()` 内で、入力検査、Metal runtime 初期化、buffer 準備、通常の `ds4_index_score` pipeline 取得を通過した後に初めて評価されます。その関数内 static のため、値はプロセス内で一度だけ cache されます。プロセス起動後でも最初の評価より前なら環境変更が反映されますが、最初の評価後に環境を変更しても再読込されません。最初の評価時に `cand != nullptr` または BF16 だった場合も値は cache され、その後の条件適合呼び出しに使われます。

値が未設定で条件を満たすと、ホスト側は `ds4_index_score_mma` pipeline を取得して dispatch し、成功した場合は `true` を返して終了します。変数が設定済み、呼び出し条件が合わない、または MMA pipeline が利用できない場合は `ds4_index_score` を dispatch します。`src/dsv41/ds4_kernels.cu` は Metal host 関数が `false` を返した場合に通常の CUDA 互換 index-score kernel へ進む構造です。

この変数の値や選択結果を出す専用ログ、警告、終了処理は見つかりません。周辺の共通準備失敗には `dsv41 metal: index_score has no host view` や `dsv41 metal: index_score rows buffer failed` の stderr 出力がありますが、これらは環境変数の判定ログではありません。

## 根拠

- 候補一覧には `DS4_NO_IDX_MMA` が載っています（`000_envvers.md:247`）。Strata ソース全体の完全一致検索では、実読み取りは `metal/src/engine/ds4_finish.cpp:1643` の一箇所、もう一箇所は直前の説明コメント（同ファイル `:1641-1642`）でした。helper 経由・動的な名前渡しの参照はありません。
- env 判定、通常 pipeline の準備、MMA 分岐、通常経路への fallthrough は `metal/src/engine/ds4_finish.cpp:1595-1600,1629-1636,1637-1670`。
- Metal 用 `index_score()` への接続と、戻り値が false の場合の fallback は `src/dsv41/ds4_kernels.cu:2356-2377`。prompt 経路の通常 indexer / 候補あり分岐は `src/dsv41/ds4_model.cu:8235-8245`、batch decode 側は `:10191-10219`。
- kernel の入出力と MMA の実装は `metal/src/engine/msl/ds4_init.metal:1201-1259,1261-1325`。性能・出力差に関する同じソース内コメント（`metal/src/engine/ds4_finish.cpp:1637-1642`）は測定条件の詳細を含まないため、この文書では再現済みの性能保証として扱っていません。
- Metal 版 DeepSeek engine の利用範囲は `docs/DEEPSEEK_MAC.md:1-4` に記載されています。

# `DS4_NO_MVN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の Metal engine が IQ matvec job を処理するとき、対応する型で MVN（複数 activation 列をまとめる専用 kernel）を選ばず、従来の IQ matvec kernel を選ぶための切替です。`DS4_NO_MVN` は CUDA/HIP/SYCL の共通 engine では読まれません。対象コードは macOS 専用の `metal/` CMake project が作る `strata_ds4` に含まれます（`metal/CMakeLists.txt:1-2,16-18,135-169`）。

## 値と判定

`std::getenv("DS4_NO_MVN") != nullptr` だけで判定し、文字列を parse しません。環境変数が設定されているかどうかが条件です。

| 状態 | `old_only` | 動作 |
|---|---:|---|
| unset | false | 対応する job は MVN kernel を選ぶ |
| 空文字を含む、何らかの値を設定 | true | 対応する job も従来の kernel を選ぶ |

`0`、`false`、空白を含む値も、設定されていればすべて true 扱いです。数値変換、値域検査、無効値時の fallback はありません。根拠: `metal/src/engine/ds4_finish.cpp:740,758-774`。

## 有効になる条件

この判定に到達するのは Metal build の IQ matvec 呼び出しで、job 数が 1〜64 の場合です。`src/dsv41/ds4_iq.cu` は `STRATA_METAL` build のみ `metal_host::iq_mv()` を呼びます（`src/dsv41/ds4_iq.cu:1694-1697`）。Metal project は macOS 以外では configure を停止し、`ds4_finish.cpp` を `strata_ds4` のソースに含めます（`metal/CMakeLists.txt:16-18,135-142,165-169`）。CLI 引数や別の環境変数による優先順位はこの判定箇所にはありません。

値が unset でも、次の job type 以外は従来 kernel のままです: 13 (Q5_K), 14 (Q6_K), 16 (IQ2_XXS), 17 (IQ2_XS), 18 (IQ3_XXS), 22 (IQ2_S), 19 (IQ1_S), 29 (IQ1_M)。これらを `tn` に対応付け、`old_only` が false の場合だけ MVN を選びます（`metal/src/engine/ds4_finish.cpp:746-758`）。

## 実行時の詳細

設定判定は `iq_mv()` 内の function-local `static const bool` です。`nj <= 0` または `ensure()` の失敗では判定行より前に戻ります。その後、最初にこの行へ到達した呼び出しで値を読み、プロセス内でキャッシュします。以降に環境を変更しても再評価されません（`metal/src/engine/ds4_finish.cpp:727-741`）。

`DS4_NO_MVN` が unset で対応 type の場合、job の列数を最大 8 列ずつに分け、各部分に応じて `ds4_*_mvn1/2/4/8` を選びます。job type が非対応、または変数が設定済みなら、列数を最大 16 列ずつに分け、type 13/14 は `ds4_iq_mv_k`、それ以外は `ds4_iq_mv` を選びます（`metal/src/engine/ds4_finish.cpp:745-775`）。対応 MVN kernel 名は Metal kernel source に定義されています（`metal/src/engine/msl/ds4_iq.metal:1172-1184`）。

Metal host の `iq_mv()` が false を返す場合、呼び出し元は通常の IQ matvec 経路へ続きます（`src/dsv41/ds4_iq.cu:1694-1711`）。この host 関数では job buffer の確保失敗時に stderr へ `dsv41 metal: iq_mv job buffer failed` を出して false を返し、pipeline 取得の例外時も false を返しますが、後者にこの関数独自のログはありません（`metal/src/engine/ds4_finish.cpp:779-794`）。環境変数による kernel 選択そのものについて、有効化・無効化のログや終了処理はありません。

## 根拠

- 読み取りと判定、type ごとの kernel 選択: `metal/src/engine/ds4_finish.cpp:727-775`。
- Metal kernel の MVN entry point: `metal/src/engine/msl/ds4_iq.metal:1172-1184`。
- Metal 呼び出し側と false 時の後続経路: `src/dsv41/ds4_iq.cu:1694-1733`。
- macOS 専用 build と `strata_ds4` への組み込み: `metal/CMakeLists.txt:1-2,16-18,135-169`。
- `docs/DETAILS.md` にこの変数の説明・測定値は見つからなかったため、性能や出力への影響は記載していません。

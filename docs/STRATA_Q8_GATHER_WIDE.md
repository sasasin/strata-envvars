# `STRATA_Q8_GATHER_WIDE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有の CUDA ソースと同梱資料を確認。外部ライブラリの環境変数は対象外。

## 役割

INT8 KV cache から選択済み cell を FP16 scratch に展開する CUDA gather で、8要素ずつ処理する wide kernel を使うか決めます。通常 kernel は thread あたり4要素、wide kernel は8要素をロードして展開します。wide kernel は `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA ビルドにだけコンパイルされ、compute capability 7.5 未満の GPU で使われます。この環境変数は wide kernel をビルドに追加したり、7.5 以上の GPU で有効化したりはしません。

## 値と判定

`pre75_q8_gather()` が初回に `getenv()` で読み、結果を関数内の `static const bool` に保存します。環境変数の文字列全体は parse せず、先頭文字だけを見ます。

| 値 | wide kernel の選択判定 |
|---|---|
| 未設定 | 有効候補（GPU の capability 判定へ進む） |
| 空文字 | 有効候補（先頭文字は `\0` で `'0'` ではない） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効。通常の4-wide kernelを使う |
| その他（例: `1`, `false`, `abc`, 空白で始まる文字列） | 有効候補。文字列の妥当性や数値としての意味は調べない |

「有効候補」でも、実際に wide kernel が選ばれるのは実験ビルドで現在の CUDA device の compute capability が 7.5 未満と確認できた場合だけです。

## 有効になる条件

- CUDA を使い、`STRATA_EXPERIMENTAL_SM60=ON` で構成されたビルドであること。この CMake option の既定値は `OFF` です。通常の ready-made engine には wide gather がコンパイルされません。
- 現在の device の capability が 7.5 未満であること。7.5 以上なら環境変数を未設定または `1` にしても4-wide kernelです。layer split などで複数 GPU が使われる場合は、各呼び出し時の current device ごとに判定します。
- 呼び出し元が `kv_gather_q8_step()` を実行すること。`src/core/layer.cpp` では、INT8 KV または hybrid KV の gather 分岐がこの関数を呼びます。ただし fast attention の分岐では別の attention kernel に進み、この gather helper を通りません。また `max_ids <= 0` なら helper は kernel を起動せず戻ります。
- QSA の KV storage が INT8 系であること。通常の `--kv fp16` や Q4 storage の gather にはこの変数は作用しません。`--kv int8` / `--kv k8v4` の設定と helper の選択は別の条件です。

current device の取得、または capability 属性の取得に失敗した場合は wide kernel を選ばず、CUDA エラー状態を `cudaGetLastError()` でクリアして通常 kernel に進みます。device ordinal が 0〜63 の範囲外の場合も通常 kernelです。取得できた capability は device ordinal ごとにキャッシュされます。

## 実行時の詳細

`kv_gather_q8_step()` は shape を検査し、`max_ids <= 0` なら終了します。実験ビルドでは `pre75_q8_gather()` が true の場合に `kv_gather_q8_wide_kernel` を256 thread/blockで起動し、起動エラーを検査して戻ります。それ以外は通常の `kv_gather_q8_kernel` を起動します。二つの kernel は同じ INT8 code と FP16 scale を使って値を FP16 scratch に書きます。ソースコメントは計算・結果が bitwise 同一で、この切替は速度だけを変えると説明しています。

環境値はプロセス内で最初に判定された後は再読込されません。プロセス実行中に環境を書き換えても判定は変わりません。環境変数自体を理由にしたログや警告はありません。kernel 起動エラー時は `kv_q8: kv_gather_q8 wide launch: <CUDA error>` または通常 kernel 用の同形式を stderr に出して終了します。

同梱資料 `docs/NVIDIA_V100.md` は `STRATA_Q8_GATHER_WIDE=0` が wide gather を無効化すると記載し、寄稿者の測定値として gather kernel の +11% を挙げています。これは gather kernel の値で、全体性能の保証ではありません。資料に測定条件の詳細はありません。

## 根拠

- CMake option の既定 `OFF` と macro 定義: `CMakeLists.txt:181-219`。
- 通常 kernel と wide kernel の要素幅、wide kernel の compile guard: `src/kernels/cuda/kv_q8.cu:76-116`。
- 環境変数の先頭文字判定、current device / capability 判定と fallback: `src/kernels/cuda/kv_q8.cu:155-177`。
- gather helper の dispatch、`max_ids` 判定、launch error 処理: `src/kernels/cuda/kv_q8.cu:205-227`。
- layer での fast attention / gather 分岐、INT8・hybrid gather の呼び分け: `src/core/layer.cpp:1261-1276`。
- CLI の `--kv` 許容値と INT8 / Q4 / hybrid mode 設定: `src/program/generate.cpp:3148-3161`。
- Q8 の storage と gather が FP16 scratch を生成する説明: `include/strata/kernels/kv_q8.hpp:1-12,40-44`。
- V100 資料の切替説明と寄稿者測定値: `docs/NVIDIA_V100.md:95-105`。

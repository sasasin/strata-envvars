# `STRATA_Q6P_SELFTEST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Q6_K 出力 head の packed kernel を登録した直後に、通常の GGUF 配置カーネルとの出力比較と実行時間の比較を行う診断用フックです。値が `2` で始まる場合は packed kernel の grid size も複数試します。通常の推論ごとに比較する設定ではありません。

この処理は CUDA 実装と SYCL 実装にあります。対象は `STRATA_Q6_PACKED` が有効で、ロードした head が Q6_K（tensor type 14）であり、packed 化の形状条件も満たす場合に限られます。CUDA/HIP の一般的な実行設定として候補一覧にありますが、確認できた読み取りは CUDA と SYCL の Q6_K kernel ソース内です。

## 値と判定

環境変数の文字列全体や数値としての妥当性は検査せず、`getenv()` が返す文字列の先頭文字だけを調べます。未設定、空文字、先頭が `1` または `2` 以外の値では何もしません。

| 値の状態 | 処理 |
|---|---|
| unset または空文字 | self-test を行わない |
| 先頭文字が `1` | 出力比較と基本の時間比較を行う |
| 先頭文字が `2` | 上記に加え grid sweep を行う |
| その他（例: `0`, `true`, `3`） | self-test を行わない |

したがって `10` も `1` と同じ、`2extra` も `2` と同じ扱いです。大文字小文字、前後の空白、後続文字は関係しません。読み取りは `native_q6_k_pack()` の呼び出しごとに行われ、プロセス起動時に値を static cache する処理ではありません。ただし呼び出しは head の初期化時だけで、実行中の環境変更をリクエストごとに反映するものではありません。

## 有効になる条件

- head のロード処理で `type_ == 14`（Q6_K）となり、`native_q6_k_packed_enabled()` が true であること。同関数は別変数 `STRATA_Q6_PACKED` が文字列全体で厳密に `"1"` の場合だけ true を返します。
- packed 化対象の重みが非 null、入力次元が正で 256 の倍数、出力行数が 2048 以上など、`native_q6_k_pack()` の形状条件を満たすこと。CUDA/SYCL 共に条件外なら pack 関数は false を返し、self-test に到達しません。
- packed 用メモリの確保とコピー、registry 登録が成功していること。

CUDA では `NativeHead` のロード、および MTP draft head の準備時に pack 関数が呼ばれます。SYCL にも同じ呼び出し条件があります。通常実行で値を有効にしても、Q6_K head がなければこの環境変数を読む処理は実行されません。

## 実行時の詳細

自己テストは固定 seed `12345` から生成した Q8_1 入力で、1〜4 列について GGUF 配置の経路と packed 経路の出力を `memcmp` で比較します。その後、1・2・4 列について各 kernel を5回ずつ実行する11組の交互測定を行い、stderr に中央値と最小〜最大の時間を出します。比較結果は `outputs BITWISE EQUAL` または `outputs DIFFER` と表示します。これは初期化時の診断であり、各推論結果を継続的に検証するものではありません。

先頭文字が `2` の場合、さらに grid `160, 320, 640, 1280, 2560, 5120, 20480` を試します。各 grid で1・2・4列を各5回実行する7組の時間を測り、`Q6_K packed grid sweep ...` を stderr に出します。この sweep は `STRATA_Q6P_GRID` の値を一時的に上書きして実行し、終了後は上書きを解除します。

比較で出力が一致しなくても、このコードはエラー終了や例外にはせず、`native_q6_k_unpack()` で packed copy を登録解除して `native_q6_k_pack()` から false を返します。通常の Q6_K 実行経路は packed kernel が使えない場合に通常の kernel へ進むため、以後は packed 経路を選びません。時間測定値は実行時に出力されますが、環境変数の有効・無効を変えたり、性能改善を保証したりする値ではありません。

## 根拠

- 値判定、比較、測定、grid sweep、不一致時の unpack: `src/kernels/cuda/native_mmvq.cu:2019-2096`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2833-2938`。
- packed kernel の grid 既定値 640 と sweep 時の override: `src/kernels/cuda/native_mmvq.cu:1818-1826,1907-1915`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2531-2539,2653-2697`。
- Q6_K head の pack 条件と呼び出し: `src/core/native_head.cpp:64-69,76-80`、`src/core/mtp.cpp:675-679`、SYCL では `sycl/src/core/native_head.cpp:89-94` と `sycl/src/core/mtp.cpp:775-779`。
- pack の形状条件と packed kernel が使えない場合の通常経路: `src/kernels/cuda/native_mmvq.cu:1918-1924,1988-1990,2347`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2705,2771-2774,3428`。
- `STRATA_Q6_PACKED` の完全一致判定: `src/kernels/cuda/native_mmvq.cu:1980-1985`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2763-2768`。
- Strata の文書では packed Q6_K を decode kernel/layout の一要素として列挙していますが、この self-test の判定値や測定結果の説明は確認できませんでした（`docs/STRIX_HALO.md:95`）。

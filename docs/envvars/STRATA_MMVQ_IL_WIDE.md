# `STRATA_MMVQ_IL_WIDE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）で、5〜8列（verify の5〜8 token）向けの行数テーブルを使うかを切り替える。無効にすると該当形状のテーブル値が常に0となり、呼び出し側は通常の `native_mmvq` にフォールバックする。2〜4列や interleaved 経路全体の有効・無効はこの変数の対象外。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 有効（`getenv` が null のため `il_env_on` は true） |
| 空文字 | 有効（先頭文字が `'0'` ではない） |
| 先頭文字が `0` の値（例: `0`, `0abc`） | 無効 |
| その他の値（例: `1`, `false`, `abc`） | 有効 |

数値変換や文字列全体の比較はせず、先頭1文字だけを `'0'` と比較する。大文字小文字は判定しない。値は5列以上のテーブル分岐が初めて評価されたとき `static const bool` に保存され、その後プロセス内では再読込されない。

## 有効になる条件

- CUDA 実装であること。HIP 側は `native_mmvq_il_supported` が常に false を返し、interleaved matvec を利用しない。
- `native_mmvq_il_supported` が、列数1〜8、`g_multi_exact`、GPU 対応条件、量子化型（IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K）を満たす必要がある。
- この変数が選ぶ5〜8列用テーブルは `sm_120` と、大規模な `sm_120` カード用キー `1201` にだけ登録されている。`sm_120` は SM 数が80以上なら `1201` に分類される。その他のGPUではテーブル値がないため、変数が有効でも通常カーネルが使われる。
- 5〜8列テーブルの個別セルが0の場合も通常カーネルへフォールバックする。`STRATA_MMVQ_IL=0` で interleaved 経路全体を無効化した場合も、この設定に関わらず通常経路となる。

## 実行時の詳細

`native_mmvq_il_rows_for` は列数が5を超える場合に `STRATA_MMVQ_IL_WIDE` を確認し、無効なら直ちに0を返す。有効なら `kIlRows58` の対応 GPU・量子化型・列数・出力行数クラス（2048、4096、8192、12288の境界）から warp あたりの行数を選ぶ。対応表は5〜8列について `sm_120` 用に定義されている。0が返ると `native_mmvq_il_supported` は false となり、`native_mmvq_il` の呼び出しは `native_mmvq` に委譲される。

この変数を読む箇所は `native_mmvq.cu` の1か所で、設定変更は上記 static 値の初期化前にプロセス環境へ反映されている必要がある。この分岐自身はログや警告を出さない。`mmvq_il_parity` のテスト・ベンチマークは `native_mmvq_il_tune` で行数を直接指定でき、その指定がある間はテーブル参照自体を迂回するため、この環境変数による制御とは別である。既存の `MMVQ_IL_TABLE.md` は `=0` が5〜8列経路を止めること、現在のテーブルが `sm_120` のみであることを説明しており、ソースと一致する。そこにある性能値は RTX PRO 5000 での資料記載値であり、本調査で再測定したものではない。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:3063-3075` — 5〜8列テーブルと `sm_120` / `1201` の登録。
- `src/kernels/cuda/native_mmvq.cu:3092-3095,3141-3155` — 値の判定、static cache、5〜8列分岐、テーブル検索。
- `src/kernels/cuda/native_mmvq.cu:3177-3193` — `sm_120` の80 SM以上をキー `1201` に分類。
- `src/kernels/cuda/native_mmvq.cu:3229-3256,3259-3269` — 対応条件、0時の通常カーネルへのフォールバック、HIP 側の無効実装。
- `src/kernels/cuda/native_mmvq.cu:3195-3198,3230-3241`、`src/kernels/mmvq_il_parity.cpp:132,168` — テスト・ベンチマークの行数指定によるテーブル迂回。
- `src/core/verify.cpp:164-165,1333-1342` — 全体スイッチ `STRATA_MMVQ_IL` と verify 中の通常 / interleaved 呼び分け。
- `docs/MMVQ_IL_TABLE.md:1-17`、`docs/DETAILS.md:2483-2485` — 関連説明との照合。

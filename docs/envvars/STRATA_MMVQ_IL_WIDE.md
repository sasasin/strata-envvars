# `STRATA_MMVQ_IL_WIDE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）で、5〜8 列用の行数テーブルを使うかどうかを制御します。unset ならこの経路は許可されます。`0` で始まる値を設定すると無効になり、対象外の GPU・量子化形式・形状では通常の `native_mmvq` にフォールバックします。

## 値と判定

値は文字列全体として parse せず、`getenv()` が返す値の先頭文字だけを調べます（`src/kernels/cuda/native_mmvq.cu:3768-3771,3832-3835`）。

| 値 | wide テーブルを許可するか |
|---|---|
| unset | 許可（既定） |
| 空文字 | 許可。設定済みだが先頭文字は `\0` で、`'0'` ではない |
| `0`、`0anything` | 不許可 |
| `1`、`false`、空白やその他 `0` 以外で始まる文字列 | 許可 |

空白除去、数値変換、全体一致、大文字小文字の判定はありません。値に不正形式としての扱いはなく、先頭文字が `0` かどうかだけで決まります。

## 有効になる条件

許可値であっても、次の条件を満たす形状・実行経路でだけ wide テーブルが選ばれます。

- CUDA 実装であること。HIP ビルドでは同じソースの HIP 側実装が `native_mmvq_il_supported()` を常に false とし、通常の matvec を呼びます（`src/kernels/cuda/native_mmvq.cu:3960-3976`）。
- 列数が 5〜8 であること。範囲外は `native_mmvq_il_rows_for()` が 0 を返します（同:3829-3835）。
- GPU compute capability が sm_80、または sm_120 で 80 個以上の SM を持つカード（内部キー `1201`）であること。wide 用のテーブルがあるのはこの二つだけです。sm_120 の 80 SM 未満のカード、Ada など他の世代ではテーブルが見つからず 0 になります（同:3720-3738,3836-3840,3872-3876）。
- sm_80 では、別の `STRATA_MMVQ_IL_SM80` と `STRATA_DEFAULTS` も表の選択に影響します。前者の先頭文字が `1` なら表を使い、`0` なら使いません。それ以外（unset、空文字など）は `STRATA_DEFAULTS=026` でなければ使います。表を使わない場合、デバイスの内部キーが 80 から 81 に置き換わるため wide 表も選ばれません（`src/kernels/cuda/native_mmvq.cu:3877-3878`, `include/strata/core/sm120_series.hpp:87-93`）。sm_120 wide 表は `STRATA_MMVQ_IL_120` の判定を通らず、同変数は 2〜4 列表の分岐にだけ適用されます（`src/kernels/cuda/native_mmvq.cu:3832-3840,3852-3859`）。
- 型が `IQ4_XS` (23)、`Q4_K` (12)、`Q5_K` (13)、`Q6_K` (14)、`Q3_K` (11) のいずれかで、該当する型・列数・出力幅の表セルが 0 でないこと。出力幅は 2048、4096、8192、12288 の境界で 5 区分されます（同:3719-3732,3831-3840,3930-3933）。
- interleaved matvec が利用可能なこと。`g_multi_exact` が false、または CUDA デバイスが対応世代でない場合、サポート判定は false です（同:3914-3933）。
- 呼び出し元が interleaved 経路を使うこと。Verifier の通常の matvec と head は別の `STRATA_MMVQ_IL` 判定も通ります。そこで無効ならこの環境変数の設定だけでは経路は有効になりません（`src/core/verify.cpp:174-175,1508-1517,2452-2464`）。
- `Q3_K` では別の `STRATA_MMVQ_IL_Q3K` 判定も有効であること。共通 helper は unset または先頭文字が `0` 以外なら有効とします（`src/kernels/cuda/native_mmvq.cu:3772-3773,3832-3836`）。

## 実行時の詳細

`native_mmvq_il_rows_for()` の 5〜8 列分岐で、関数内 `static const bool` として初回に判定・保存されます。初回照会後にプロセス環境を変更しても再評価されません。これは起動時の一括読み取りではなく、この行数表の初回照会時です（`src/kernels/cuda/native_mmvq.cu:3829-3835`）。

設定が許可され、GPU と表セルが条件に合えば、戻された行数で `launch_il_rows` が対象の interleaved kernel を起動します。条件を満たさず行数が 0 の場合、`native_mmvq_il_supported()` は false となり、Verifier は通常の `native_mmvq` を呼びます。また `native_mmvq_il()` 自身も非対応時には `native_mmvq()` に委譲します（同:3930-3957、`src/core/verify.cpp:1508-1517`）。この切替について専用の警告・ログや終了経路はありません。

Strata の `docs/MMVQ_IL_TABLE.md` はこの変数を 5〜8 列経路のスイッチとして説明していますが、「sm_120 だけに表がある」とする説明はこの commit の実装と一致しません。同ソースには sm_80 用の `kIlRows58_80` と、sm_120 / 80 SM 以上向けの `kIlRows58_120` が定義されています（`docs/MMVQ_IL_TABLE.md:8-10`, `src/kernels/cuda/native_mmvq.cu:3715-3732`）。sm_80 表についてソースコメントは CMP 170HX での測定としています（同:3727-3732）。`docs/DETAILS.md` も `STRATA_MMVQ_IL_WIDE=0` で 5〜8 列経路を無効にできると記載しています（`docs/DETAILS.md:1231-1232`）。これらの測定記述は資料上の報告であり、本調査では build、GPU 実行、性能測定を行っていません。

## 根拠

- 値の読み取りと変換: `src/kernels/cuda/native_mmvq.cu:3768-3771,3832-3835`
- 列数・GPU 世代・表セルの条件: `src/kernels/cuda/native_mmvq.cu:3715-3738,3829-3840,3872-3876`
- interleaved 経路の対応判定と非対応時の fallback: `src/kernels/cuda/native_mmvq.cu:3914-3957,3960-3976`
- Verifier 側の呼び出し条件と通常 matvec への分岐: `src/core/verify.cpp:174-175,1508-1517,2452-2464`
- Strata の説明資料: `docs/MMVQ_IL_TABLE.md:8-13`, `docs/DETAILS.md:1231-1232`

# `STRATA_MMVQ_IL_120`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）で、compute capability 12.0 かつ 80 個以上の SM を持つ GPU が、2〜4 列の行数テーブルとして `kIlRows_120` を使うか、共有テーブル `kIlRowsShared` を使うかを選びます。変わるのは各 warp が処理する行数と、その shape で interleaved kernel を使うかどうかです。5〜8 列の経路は別の `STRATA_MMVQ_IL_WIDE` 判定、1 列は専用分岐を使うため、この変数の対象外です。

## 値と判定

`il_env_on()` は `std::getenv()` の結果を文字列全体として parse せず、未設定か、先頭文字が `'0'` かだけを判定します（`src/kernels/cuda/native_mmvq.cu:3768-3771`）。空文字は設定済みですが先頭文字が `'0'` ではないため有効扱いです。

| 値 | `own120` | 80 SM 以上の sm_120 でのテーブル選択 |
|---|---:|---|
| 未設定 | true | `kIlRows_120` |
| 空文字 | true | `kIlRows_120` |
| 先頭文字が `0`（`0`, `0abc` など） | false | `kIlRowsShared` |
| その他（`1`, `true`, `false`, `2` など） | true | `kIlRows_120` |

数値変換、範囲検査、大文字小文字の正規化はありません。判定結果は `static const bool own120` に初回評価時から保存され、同じプロセスで後から環境を書き換えても再評価されません（`src/kernels/cuda/native_mmvq.cu:3855-3857`）。

## 有効になる条件

- CUDA 実装であること。HIP 側は `native_mmvq_il_supported()` が常に `false`、行数問い合わせが常に 0 を返し、`native_mmvq_il()` は通常の `native_mmvq()` に委譲します。その分岐にこの環境変数の読み取りはありません（`src/kernels/cuda/native_mmvq.cu:3960-3976`）。
- GPU が compute capability 12.0 で、SM 数が 80 以上であること。デバイス属性から 12.0 のカードを 80 SM 以上なら内部キー `1201` に置き換えます。80 未満の sm_120 はキー `120` のままで共有テーブルです（`src/kernels/cuda/native_mmvq.cu:3863-3881`）。
- native MMVQ の interleaved 経路を使う shape であること。候補テーブルは 2〜4 列（`ncols`）、対応する量子化型 IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K です。テーブル値 0 のセルは plain `native_mmvq` を使います（`src/kernels/cuda/native_mmvq.cu:3829-3860,3930-3957`）。
- `STRATA_MMVQ_IL` が無効化していないこと。verify の呼び出し側は、未設定または先頭文字が `0` でない場合に interleaved 経路を候補にし、`STRATA_MMVQ_IL=0` ならこの変数が有効でも候補にしません（`src/core/verify.cpp:175,1495-1517`）。
- `STRATA_MMVQ_IL_ROWS` に同じ型・列数の有効な上書き行がないこと。該当行はアーキテクチャ別テーブルより先に返されます。この上書きは全 GPU 向けです（`src/kernels/cuda/native_mmvq.cu:3795-3825,3842-3843`）。また Q3_K は `STRATA_MMVQ_IL_Q3K=0` でテーブル選択前に無効になります（同 `:3852-3853`）。

`native_mmvq_il_supported()` はさらに `g_multi_exact` とアーキテクチャ適格性を要求します。verify 側ではこの問い合わせが偽なら通常の `native_mmvq()` に進みます（`src/kernels/cuda/native_mmvq.cu:3914-3933`; `src/core/verify.cpp:1508-1517,1551-1560,1791-1798,2452-2464`）。

## 実行時の詳細

sm_120 の 80 SM 以上のカードは `il_cc()` がキー `1201` になります。2〜4 列の問い合わせで、既定（未設定）または先頭文字が `0` 以外なら `kIlRows_120` を選び、先頭文字が `0` なら条件式が専用表の選択を抑止し、初期値の `kIlRowsShared` を維持します（`src/kernels/cuda/native_mmvq.cu:3658-3667,3853-3859,3863-3876`）。共有表に戻す場合も interleaved 経路全体を止めるとは限りません。共有表の該当セルが 0 なら `native_mmvq_il_supported()` が false となり、呼び出し元が通常の `native_mmvq()` を使います。

verify の window 処理では GDN/QSA の dense projection や loaded head projection からこの適格性判定とカーネル呼び出しに至ります。2〜4 列では必要に応じて q8_1 入力の interleaved copy を作り、適格なら `native_mmvq_il()`、それ以外は `native_mmvq()` を呼びます（`src/core/verify.cpp:1491-1517,1547-1560,1788-1798,1838-1849,2452-2464`）。表は量子化型・列数・出力行数クラスごとに warp あたり 0/1/2/4 行を記録します（`src/kernels/cuda/native_mmvq.cu:3661-3667,3830-3831,3858-3859`）。Strata の資料は、表が plain kernel と同じ出力 bit になる設計で、表の差は速度だけと説明しています（`docs/MMVQ_IL_TABLE.md:3-7,17`）。

この変数について専用のログ、警告、エラー出力はありません。無効値を検査して失敗する処理もなく、先頭文字が `0` でない値は有効扱いです。テーブル行が 0、他の条件が不足、または HIP の場合は plain `native_mmvq()` へ進みます（`src/kernels/cuda/native_mmvq.cu:3930-3940,3968-3973`）。資料 `docs/DETAILS.md:1229-1234` は sm_120 の 2〜4 列用テーブルとして本変数を挙げています。カード別の行選択根拠と共有テーブルへの切替条件は `docs/MMVQ_IL_TABLE.md:12-21` に記載されています。

## 根拠

- 候補名のコード参照と読み取り: `src/kernels/cuda/native_mmvq.cu:3855`。値判定 helper: 同 `:3768-3771`。
- sm_120 専用テーブル: `src/kernels/cuda/native_mmvq.cu:3658-3667`。
- アーキテクチャ選択、SM 数による `120` / `1201` 分岐: `src/kernels/cuda/native_mmvq.cu:3853-3859,3863-3881`。
- 対象 shape、fallback、HIP 分岐: `src/kernels/cuda/native_mmvq.cu:3829-3860,3930-3976`。
- verify の実呼び出しと上位スイッチ: `src/core/verify.cpp:175,1491-1517,1547-1560,1788-1798,1838-1849,2452-2464`。
- 関連資料: `docs/MMVQ_IL_TABLE.md:3-21`; `docs/DETAILS.md:1229-1234`。

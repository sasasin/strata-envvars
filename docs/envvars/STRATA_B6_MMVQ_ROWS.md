# `STRATA_B6_MMVQ_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の native multi-column MMVQ で、対応する重み形式について、各 activation column の fragment を weight block ごとに一度読み、複数出力行で再利用する B6 rows kernel を選びます。対象は `Q4_K`、`Q5_K`、`Q6_K`、`IQ4_XS` です。`Q8_0` を含む未対応形式ではこの kernel を使わず通常の multi-column kernel に進みます。B6 の出力は既定の exact layout と bitwise 一致する設計です（`engine/src/kernels/cuda/native_mmvq.cu:1408-1413,1414-1418,1451-1476,1551-1569`）。

## 値と判定

値は `std::getenv` の結果を `std::atoi` に渡します。未設定なら `0`、明示的な空文字や数値に変換できない文字列も `atoi` により `0` です。文字列全体の妥当性検査はなく、先頭の空白や符号付き整数として読める接頭部は変換され、後続文字は無視されます（例: `" 1tail"` は `1`、`"0anything"` と `"true"` は `0`）。大文字小文字の扱いはありません。負値も拒否されず、0 以下として B6 を無効にします。`atoi` が表現できない範囲の値はコードで処理を定義していません（`engine/src/kernels/cuda/native_mmvq.cu:1247-1250,1560-1568`）。

| 実行経路 | unset / 空文字 / 0 | 正の整数 | 負の整数 |
|---|---|---|---|
| CUDA/HIP の B6 判定 | 0 以下なので不使用 | B6 を要求。`1` または `2` は 2 行、`8` は 8 行、それ以外の正数は 4 行の kernel を選択 | 不使用 |
| CUDA の対応 GPU で起動時既定値が設定された場合 | unset のみ `1` に補完。空文字や `0` は利用者の値として維持 | 上と同じ | 上と同じ |

`1` は内部で 2 行に変換されます。値 `2` も 2 行、`8` は 8 行です。それ以外の正数（たとえば `3`、`4`、`5`）は 4 行の kernel に入ります。正数を行数としてそのまま使うわけではありません（`engine/src/kernels/cuda/native_mmvq.cu:1561-1568`）。

## 有効になる条件

- GPU native MMVQ を使う CUDA または HIP 経路であること。CUDA の起動時既定値設定は HIP と Metal を除外するコンパイル条件の内側にありますが、カーネル側の環境読み取り自体は CUDA/HIP 共通ファイルにあります（`engine/src/program/generate.cpp:4421-4428`, `engine/src/kernels/cuda/native_mmvq.cu:1247-1250`; `terminal/data/settings-register.json:2140-2150` は登録 backend を `cuda-hip` としています）。
- 対象形式が `Q4_K`、`Q5_K`、`Q6_K`、`IQ4_XS` であること。その他の形式では `B6X<F>::ok` が false となり B6 起動関数が false を返します（`engine/src/kernels/cuda/native_mmvq.cu:1414-1418,1451-1476,1554-1557`）。
- 複数 column の native MMVQ であること。通常の `launch_multi` は `ncols=2..8` を個別 dispatch し、それより多い列は分割します。単列経路では `launch_multi_n` を通らないため、この変数の対象外です（`engine/src/kernels/cuda/native_mmvq.cu:1713-1742`）。
- `g_multi_exact` が true であり、`n_in / F::DIV >= 1` であること。現在 `g_multi_exact` は初期値 true ですが、無効または形状条件を満たさなければ B6 起動関数は false を返して通常 kernel に進みます（`engine/src/kernels/cuda/native_mmvq.cu:1246,1560-1569,1681-1690`）。
- CUDA では、Dense INT8 Tensor Core 経路が `native_mmvq` の先行条件を満たして成功した場合、その時点で戻るため B6 は呼ばれません。また CUDA の interleaved MMVQ がその型・形状をサポートする場合も専用 kernel を使い、サポートしない場合だけ `native_mmvq` に戻ります（`engine/src/kernels/cuda/native_mmvq.cu:3775-3800,4230-4237`）。HIP の interleaved API は常に `native_mmvq` に委譲します（同 `:4255-4268`）。
- `STRATA_TSUM=1` との組合せでは、B6 が適用可能なら B6 が先に選ばれます。B6 対象外の形式などで B6 が辞退した場合は後続の通常経路が判定します（`engine/src/kernels/cuda/native_mmvq.cu:1558-1560,1681-1685`）。

CUDA の `apply_nv_defaults` は、GPU 数・能力値が取得でき、全可視 GPU の compute capability が同じ場合に呼ばれます。表は sm_86 / sm_89 / sm_70 / sm_60 でこの変数を `1` に設定します。sm_86 は `STRATA_SM86_PERF=0`、sm_89 は `STRATA_SM89_PERF=0` または `STRATA_DEFAULTS=026`、sm_70 は `STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026`、sm_60 は `STRATA_SM60_PERF=0` で表自体が無効になります。sm_60 の当該分岐には `defaults026` 判定がありません。sm_120 / sm_121 の表にはこの変数がありません。すでに環境に名前が存在すれば、その値が空文字や `0` であっても既定値で上書きされません。混在 compute capability の複数 GPU ではこの自動既定値適用をスキップします（`engine/src/core/nv_defaults.cpp:41-43,58,75-90,136-175,176-180,222-234`; `engine/src/program/generate.cpp:4421-4453`）。

## 実行時の詳細

`g_b6_rows` は初期値 `-1` です。B6 判定の初回呼び出しで環境値を読み、`g_b6_rows >= 0` になれば以後その値を使います。従って通常の unset / 空 / 0 / 正数は初回利用時に cache され、実行中に環境を変更しても反映されません。負数に変換された値では `g_b6_rows < 0` のままなので、次の判定呼び出しでも再読込されます。カーネルのロード時ではなく初回使用時に読む設計であり、CUDA の architecture defaults が先に環境へ設定されるよう、engine 起動処理ではその設定を GPU kernel の switch 読み取りより前に行います（`engine/src/kernels/cuda/native_mmvq.cu:1247-1250,3272-3275`; `engine/src/program/generate.cpp:4422-4428,4448`; `engine/src/core/nv_defaults.cpp:222-234`）。

B6 は 2、4、または 8 出力行を block 単位で処理し、各 column の activation fragment を weight block ごとに一度ロードしてその行群へ再利用します。`b6_launch` が使わないと判断すると false を返し、呼び出し元は Q8 Volta 専用経路または既定の exact multi-column kernel へ進みます。カーネル選択結果による専用の stdout/stderr ログはありません（`engine/src/kernels/cuda/native_mmvq.cu:1408-1413,1505-1549,1551-1570,1677-1710`）。

## ログと測定値

この変数の値や B6 の採否を直接表示するログはありません。CUDA の architecture defaults が値を設定した場合、`apply_nv_defaults` は stderr に `strata: sm_86 (Ampere): ... speed switches on by default ...` などの行を出し、設定した switch 名を列挙します。既定値一覧が空、またはこの変数が既に設定済みで他に追加された既定値もなければ、この行は出ません（`engine/src/core/nv_defaults.cpp:227-255`）。

Strata の `docs/DETAILS.md:1293-1300` はこの経路を exact とし、sm_86 と sm_60 で既定 on と記載しています。現行ソースの既定値表には sm_89 と sm_70 も含まれます（`engine/src/core/nv_defaults.cpp:75-90,136-175`）。`docs/DETAILS.md:1710` には 0.1.45 の RTX 3060 / RTX A4000、IQ3_XXS、30K prompt 後の decode における B6 の集計値がありますが、該当表は B6 固有のペア数や測定内訳を示していないため、ここでは性能値を一般化しません。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:1246-1250` — 初期状態、環境読み取り、変換、初回評価。
- `engine/src/kernels/cuda/native_mmvq.cu:1408-1418,1451-1476` — 対応形式と B6 の計算実装。
- `engine/src/kernels/cuda/native_mmvq.cu:1551-1570,1677-1710` — mode から行数への対応、fallback、起動順。
- `engine/src/kernels/cuda/native_mmvq.cu:1713-1742,3775-3819,4230-4268` — column 数、上位経路、型 dispatch、CUDA/HIP の interleaved 経路。
- `engine/src/core/nv_defaults.cpp:41-43,58,75-90,136-175,176-180,222-255`; `engine/src/program/generate.cpp:4421-4453` — CUDA architecture defaults と適用時期・優先順位・ログ。
- `terminal/data/settings-register.json:2140-2155` — Strata の設定台帳上の backend / 読み取り登録。
- `docs/DETAILS.md:1293-1300,1710` — Strata 資料との照合（既定値の記載範囲、歴史的な測定の所在）。

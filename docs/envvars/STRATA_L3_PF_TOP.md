# `STRATA_L3_PF_TOP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`STRATA_L3_PF` による次層 CPU expert prefetch が有効なとき、次層で先読み候補にする「VRAM にない expert」の上限数を指定します。既定値は 4、設定時は 1〜16 に丸められます。環境変数を読むのは `engine/src/program/generate.cpp` の generate 初期化経路だけです。単独で prefetch を有効化する設定ではありません（同ファイル:10410-10418,10425-10444）。

## 値と判定

prefetch の構成が成功した後、初期化中に `std::getenv` で設定有無を確認し、設定があれば `std::atoi` の結果を `std::max(1, std::min(16, ...))` で制限します。unset の場合は `Drive::l3_top` の初期値 4 が使われます（`engine/src/program/generate.cpp`:1592-1597,10425-10444）。

| 条件 | unset | 設定時の変換例 | 無効値の扱い |
|---|---|---|---|
| prefetch 構成成功時 | 4 | `1`〜`16`。整数として読めた値は範囲内に制限される（例: `2`, `17`→16） | 専用の無効値判定はなく、変換後の整数を 1〜16 に丸める。0、負値、空文字、`false`、`0anything` は 1。`2tail` は 2 |

`atoi` は文字列全体の厳密な検証ではなく、先頭の空白と符号を許し、10進数として読める先頭部分を変換します。したがって ` 2` や `+2` は 2、`2.5` は 2、`true` は 0 から 1 になります。大文字小文字や後続文字を検査する分岐はありません。整数範囲外の文字列に対する `atoi` の結果はこのコードで検証・処理されません。範囲制限は変換後にだけ行われます（同ファイル:10442）。

## 有効になる条件

- `STRATA_L3_PF` が有効で、native expert pool の static slices が使える必要があります。`STRATA_L3_PF` が unset または空文字なら、`l3_pf_auto_default` は総 VRAM が 0 でなく 13 GiB 以下、VRAM 常駐 expert が総数の半分未満、pool worker が 8 以上のときに自動で有効にします。非空値は `atoi(...) != 0` で判定されます。`STRATA_L3_PF=0` などで無効なら、この変数は読み取られません（`engine/include/strata/core/low_vram_rules.hpp`:118-125、`engine/src/program/generate.cpp`:10414-10425）。
- `--no-pool` でなく、expert layout が native であり、pool が NUMA split なし・複数 worker の static slices を実際に有効化できる必要があります。`STRATA_POOL_STATIC` は static slices だけを要求できますが、それだけでは `want_pf` は true にならず、L3 prefetch は始まりません（`engine/src/program/generate.cpp`:10414-10425、`engine/include/strata/kernels/cpu/pool.hpp`:254-271）。
- この読み取りと設定は CUDA API を使う `generate.cpp` の経路です。さらに、expert の RAM copy を示す `FileExpertSource` または `ArenaExpertSource`、AVX2 対応 CPU、各層の BF16 router weights が必要です。GPU stages が空でない場合も router 構築を見送ります。索引 `docs/SETTINGS.md` は NVIDIA と AMD の候補として載せていますが、この TOP の実読み取りは本 commit では CUDA generate 側の一箇所です。条件が揃わなければ `STRATA_L3_PF_TOP` は参照されず、`STRATA_L3_PF` が要求されていても prefetch は構成されません（`engine/src/program/generate.cpp`:10425-10448）。
- TOP の値を設定する CLI 引数・設定ファイルによる上書きは、この名前の実読み取り箇所にはありません。`STRATA_L3_PF_TOP` は prefetch の有効・無効を選ばず、上記条件成立時の候補数だけを変えます。

## 実行時の詳細

値は generate の pool 構成時に一度読み、`Drive::l3_top` に保持されます。実行中にプロセス環境を変えても再読込されません。未設定なら構成時に初期値 4 が残ります（`engine/src/program/generate.cpp`:1592-1597,10425-10444）。

`drive_pool_multi_impl` は次層の router、入力、GPU 常駐 expert の情報、`l3_top` を `L3Prefetch` に渡します。単一層用の `drive_pool` には同様の prefetch 呼び出しがなく、TOP はその経路では使われません。pool は static slices 等を確認して非同期の prefetch batch を開始し、worker は入力に対する router の票から VRAM 非常駐 expert を最大 `top` 個選び、その RAM blob の担当 row を読みます。候補に正票がない場合や blob がない場合、実際に読む数は上限より少なくなります。次の pool batch は実行中の prefetch を停止します。この経路は次層の候補データを読むもので、値をモデル計算の入力に反映しません（`engine/src/program/generate.cpp`:1628-1653、`engine/include/strata/kernels/cpu/pool.hpp`:260-271、`engine/src/kernels/cpu/pool.cpp`:1620-1633,1696-1742）。

## ログと測定値

構成が成功すると stderr に `strata generate: L3 prefetch on: the next layer's top %d non-resident experts, %lld MiB of routers in RAM` が出て、丸め後の上限数を表示します。router などの前提条件を満たさない場合は `strata generate: L3 prefetch off (needs the RAM copy, AVX2, one GPU and BF16 routers)` が出ます。TOP の不正値に対する専用警告はありません。`docs/DETAILS.md`:1245 は L3 prefetch 全体について RTX 3090（PCIe 4.0 x8）、Ryzen 9 5950X、DDR4 での測定と top 2〜8 の比較を記載していますが、TOP 単独の性能値とはしていません。測定記述はソースコード上の挙動の根拠ではありません。

## 根拠

- `engine/src/program/generate.cpp`:1592-1597,10410-10448 — 初期値、値の読み取りと丸め、構成条件およびログ。
- `engine/include/strata/core/low_vram_rules.hpp`:118-125 — 親設定 `STRATA_L3_PF` の自動判定。
- `engine/src/program/generate.cpp`:1628-1653 — 次層 prefetch の呼び出しと TOP の引き渡し。
- `engine/include/strata/kernels/cpu/pool.hpp`:254-271、`engine/src/kernels/cpu/pool.cpp`:1620-1633,1696-1742 — worker の prefetch 開始、候補選択と RAM blob 読み出し。
- `docs/DETAILS.md`:1245 — L3 prefetch 全体に関する測定記述。

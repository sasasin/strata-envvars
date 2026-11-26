# STRATA_BATCH_GDN_GROUPS

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

バッチ検証 window の GDN recurrence を slot ごとに呼び出す代わりに、最大 8 slot group をまとめた gdn_step_norm_groups 呼び出しへ切り替える。対象は recurrence の計算・state 更新であり、GDN の convolution history commit は引き続き slot ごとに処理する。CUDA/HIP は engine/src/core/verify.cpp、SYCL は engine/sycl/src/core/verify.cpp で読み取る。どちらも通常の単独 window ではなく、batch window の記録または commit の経路で分岐する（engine/src/core/verify.cpp:1979-1993, 4741-4773; engine/sycl/src/core/verify.cpp:1277-1295, 3427-3464）。

## 値と判定

読み取り値は std::atoi の結果が 0 かどうかで判定する。文字列全体の妥当性検査はなく、数値接頭辞を変換する。したがって未設定は 0、空文字・0・0anything・true・false・-0 は無効、1・-1・2x・+1・先頭空白の後の 1 は非ゼロで有効になる。先頭空白を読み飛ばした後も数値で始まらない値は 0 になる。大文字小文字を比較する処理はない。実装は CUDA/HIP で共通 helper、SYCL では各読み取り箇所の同じ atoi 判定である（engine/src/core/verify.cpp:375-377, 392; engine/sycl/src/core/verify.cpp:1278-1281, 3427-3430）。

| 実行経路 | unset（注入後） | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Linux CUDA、--batch が 2 以上 | "1" を設定 | atoi が非ゼロの値 | atoi が 0 の値。unset は注入により有効 |
| HIP、Windows gfx1151 で --batch が 2 以上、かつ STRATA_GFX1151_DEFAULTS が '0' で始まらない | "1" を設定 | atoi が非ゼロの値 | atoi が 0 の値。unset は注入により有効 |
| HIP、discrete RDNA3 (gfx1100/gfx1101/gfx1102) で --batch が 2 以上、かつ gfx11 defaults が有効 | "1" を設定 | atoi が非ゼロの値 | atoi が 0 の値。unset は注入により有効 |
| 上記以外の CUDA/HIP、または SYCL | unset は 0 | atoi が非ゼロの値 | atoi が 0 の値 |

これらの既定設定は名前が環境に既に存在すれば値を変えない。明示した空文字も「設定済み」として保たれ、変換結果は 0 になる。Linux CUDA の既定は Linux CUDA build で --batch >= 2 の場合に適用される。HIP の gfx1151 既定は Windows かつ gfx1151 の場合で、STRATA_GFX1151_DEFAULTS が '0' で始まると適用しない。discrete RDNA3 既定は STRATA_GFX11_DEFAULTS が '0' で始まる場合、または STRATA_DEFAULTS=026 の場合に適用しない（engine/src/program/generate.cpp:4287-4320, 4410-4415; engine/src/core/arch_defaults.cpp:218-245, 248-260, 302-357; engine/include/strata/core/gfx11_extra.hpp:27-31, 117-133）。

docs/BATCHING.md:716 は両 switch を既定で off と説明する。これは上記の platform defaults が適用されない経路では一致するが、現行ソースは Linux CUDA の --batch >= 2 と一部 HIP GPU 条件で未設定値に "1" を注入するため、全 platform に対する説明ではない（engine/src/core/arch_defaults.cpp:240-260, 302-357; engine/src/program/generate.cpp:4410-4415）。

## 有効になる条件

- GDN 層があり、slot をまとめて処理する batch verifier 経路に入ること。batch_rec_ が false の通常経路ではこの変数による分岐は使われない（engine/src/core/verify.cpp:1979; engine/sycl/src/core/verify.cpp:1282）。
- batch window 内の recurrence は、その層の row 範囲 te - tb が 8 以下の場合に group kernel を使う。8 を超えると従来の slot ごとの recurrence ループへ進む（engine/src/core/verify.cpp:1979-2003; engine/sycl/src/core/verify.cpp:1282-1305）。
- batch commit 側は S <= 8 かつ各隣接 row が異なる slot の場合に限り、recurrence の group kernel に slot ごとの 1 row をまとめる。複数 proposal を含む slot などこの条件を満たさない場合は従来の per-slot recurrence に戻る。STRATA_BATCH_SELF_COMMIT により window 自体が commit を担う経路では commit graph は作られず、window 内の分岐が適用対象となる（engine/src/core/verify.cpp:4710-4713, 4741-4773; engine/sycl/src/core/verify.cpp:3431-3464）。
- --batch-mtp は変数の値を上書きしないが、同じ slot に複数 proposal row が並ぶと one-row commit 条件を満たさなくなることがある。window 内の recurrence は row group が 8 以下なら別途有効になり得る（engine/src/core/verify.cpp:1490-1495, 1979-1993, 4741-4768）。
- Terminal の serve 経由では、サーバーは親プロセス環境を子 engine 環境へコピーし、その後 run config の env を同名キーにも適用する。run config の値が親環境値より優先し、engine の platform defaults はキーが存在しない場合だけ設定する（terminal/serve/server.py:4007-4028; engine/src/core/arch_defaults.cpp:253-260, 307-310, 321-323）。

## 実行時の詳細

CUDA/HIP の batch_gdn_groups_on() は初回呼び出し時に static const bool へ値を保存し、window 内 recurrence と batch commit の双方から参照する。SYCL は window capture 内と commit capture 内にそれぞれ別の関数ローカル static を持ち、各箇所で初めて実行されたときの値を保存する。したがって、読み取り後にプロセス環境を変更しても、その static の判定は更新されない（engine/src/core/verify.cpp:373-377, 392; engine/sycl/src/core/verify.cpp:1278-1281, 3427-3430）。

有効時は各 slot の state、row 開始位置、row 数（commit 時は keep 数も）を GdnGroups に詰め、group kernel を呼ぶ。実装は group 数 1〜8 を検査し、CUDA/HIP では一つの CUDA kernel launch、SYCL では一つの parallel_for に渡す。無効時または適用条件外では既存の per-slot recurrence 呼び出しを使う。設定値の不正を理由に終了したり、fallback 警告を出したりする処理はこの変数の読み取りにはない（engine/src/core/verify.cpp:1980-2003; engine/src/kernels/cuda/verify_kernels.cu:1296-1317; engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2146-2175）。

## ログと測定値

CUDA/HIP の batch verifier は STRATA_BATCH_ATTN_ROWS またはこの変数のいずれかが有効なら、stderr に次の format string の行を出す。各 %s は on/off と switch 名、末尾の %s は該当時の KV streaming 補足（または空文字）に置き換わる。両 switch が無効ならこの行は出ない。このログは verifier stage ごとの初期化時に評価される。SYCL の同じ verifier 初期化箇所には、この switch の状態を表示する行はない（engine/src/core/verify.cpp:4661-4673; engine/sycl/src/core/verify.cpp:3319-3325）。

    strata verify: batch rows in one launch: attention %s (STRATA_BATCH_ATTN_ROWS), GDN %s (STRATA_BATCH_GDN_GROUPS)%s\n

HIP の architecture defaults が未設定値を注入した場合は、gfx1151 または RDNA3 の parallel-request switches を列挙する stderr 行に BATCH_GDN_GROUPS が含まれる。Linux CUDA の parallel default 注入自体にはこの switch を列挙するログがない（engine/src/core/arch_defaults.cpp:253-260, 346-357, 433-442）。測定値はここでは記載しない。

## 根拠

- 候補一覧: docs/envvars/000_envvers.md:803（候補名のみ。実装の根拠にはしていない）。
- CUDA/HIP 読み取り・判定・cache: engine/src/core/verify.cpp:373-377, 392。
- CUDA/HIP window recurrence と group 数制限につながる処理: engine/src/core/verify.cpp:1979-2003; kernel launch と引数検査: engine/src/kernels/cuda/verify_kernels.cu:1296-1317。
- CUDA/HIP batch commit と one-row 条件: engine/src/core/verify.cpp:4710-4713, 4741-4773。
- SYCL の読み取り・window recurrence・commit: engine/sycl/src/core/verify.cpp:1277-1305, 3427-3464; group kernel: engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2146-2175。
- 既定値の適用: Linux CUDA engine/src/program/generate.cpp:4410-4415, engine/src/core/arch_defaults.cpp:248-260; HIP engine/src/program/generate.cpp:4287-4320, engine/src/core/arch_defaults.cpp:240-245, 302-357, engine/include/strata/core/gfx11_extra.hpp:27-31, 117-133。
- batch 状態・ログ: engine/src/core/verify.cpp:4661-4673, 4684-4690; Terminal 子 engine 環境: terminal/serve/server.py:4007-4028。

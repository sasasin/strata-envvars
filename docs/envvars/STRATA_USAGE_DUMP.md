# `STRATA_USAGE_DUMP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象はStrata所有ソース。外部ライブラリ・ドライバーの動作は含めない。

## 役割

SYCLエンジンの speculative decode で、device plan が処理したexpert routingをカウントし、終了時に指定ファイルへトレースとして書き出します。カウンターはexpert profile作成ツールが読む形式で、各routing entryを `k=1`、weight `0` のレコードとして出します。通常の利用者向け推論設定ではなく、profile用トレースを作る診断・データ収集フックです。

この名前をソースで読む箇所は `sycl/src/program/generate.cpp` の1箇所です。CUDA/HIP実装では読み取りを確認できません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | カウンターを割り当てず、usage traceを出力しない |
| 空文字 | 未設定と同様。`getenv` は非NULLでも `*usage_dump` がfalseなので無効 |
| 非空文字列 | その文字列を出力パスとして保持する。数値変換や内容の検証はしない |

値は speculative decode の経路に入った後、一度 `getenv("STRATA_USAGE_DUMP")` で読み取られます。この実行中に環境を書き換えても再評価されません。`fopen(path, "wb")` はdecode完了後に行い、既存ファイルがあれば上書きします。ファイルを開けない場合、usage出力箇所では警告やエラーを出さず、`usage dumped` の表示も出しません。`fwrite` と `fclose` の戻り値は検査されないため、この表示だけでは全データの書き込み完了を保証しません。

## 有効になる条件

環境変数が非空でも、次の条件を満たす必要があります。

- SYCLエンジンの speculative decode 経路を通ること。この読み取りと出力は speculative decode ブロック内にあります。
- `mirror_table_d` が作成されていること。これは `--stream-experts`、GGUF由来のexpert source、`--expert-cache > 0` などの条件下で、VRAM外expertのミラーに成功した経路で設定されます。

したがって、非空パスを指定しただけでは出力は保証されません。mirror table がない場合はdevice counterを割り当てず、ファイルも開きません。`STRATA_VERIFY_NO_HOST` 使用時にもdevice-side counterで記録できる、と同梱ツールの説明にありますが、この環境変数自体が `STRATA_VERIFY_NO_HOST` を有効化するわけではありません。

## 実行時の詳細

`g.n_layers * g.n_expert` 個の `int32_t` counterをdevice memoryに確保し、ゼロ初期化してからresident planへ渡します。resident plan kernelは、各layerのrouting IDごとに、有効なexpert IDのcounterをdevice-side atomic incrementします。そのため、これは異なるexpert数ではなくrouting entryの出現回数です。記録対象はこのdevice planが処理するverify windowのroutingで、prompt prefillのrouting記録ではありません。

decode完了時にcounterをhostへコピーし、layer、expertの昇順で、counterの回数だけレコードを出します。各レコードは16 byteで、`int32 layer, int32 k=1, int32 expert_id, float weight=0` です。weightを使った頻度ではなく、profileツールが出現回数を集計できるよう、ゼロweightのレコードを繰り返します。ファイルを開けた場合、stdoutに `usage dumped <path> (<count> routed entries counted on the device)` を表示します。

この形式は `tools/make_profile_mix.py` が `--dump-routing` と同じ形式として受け取り、`tools/make_profile.py` のtrace readerがlayer、expertの出現頻度を数えます。`tools/collect_profile_traces.py` は既定の `usage` モードで子engineの環境にこの変数を設定し、promptごとのtraceを集めます。

## 根拠

- `sycl/src/program/generate.cpp:12024-12025,12059-12065` — speculative decode内の読み取り、mirror table条件、counterの確保・初期化・resident planへの登録。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2081-2114,2363-2394` — plan kernelへのcounter引き渡しとrouting IDごとのatomic count。
- `sycl/src/program/generate.cpp:12512-12528` — counterのreadback、`wb` での出力、レコードの値、成功時の表示。
- `tools/collect_profile_traces.py:9-18,63-85` — `usage` モードが子engineへ環境変数を渡すこと、およびtrace収集の説明。
- `tools/make_profile_mix.py:9-12`、`tools/make_profile.py:47-58` — trace形式と集計方法。
- `docs/INTEL.md:824-829` — SYCL device-side routing countを使ったprofile作成の説明と、資料記載の測定結果。測定値はこの調査で再計測していない。

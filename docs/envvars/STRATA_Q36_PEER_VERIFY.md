# `STRATA_Q36_PEER_VERIFY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 GPU エンジンの peer tier が計算した expert 行を、CPU expert pool でも計算して照合するためのホスト側バッファを確保する診断スイッチです。対象名は値の内容を解釈せず、設定されているかだけを見ます。通常の peer 行は `cpu_out` に入り、`STRATA_Q36_PEER_VERIFY` による CPU の照合結果は別バッファ `cpu_chk` に入るため、照合結果を推論出力へ採用する処理ではありません（`engine/src/qwen35/q36_engine.cu:1828-1829,3346-3349,3364-3391`）。

この実装は `engine/src/qwen35/q36_engine.cu` の Qwen3.6-35B-A3B GPU エンジンにあります。CPU expert pool のビルドで、expert が VRAM に収まらず hybrid 配置へ進むときにバッファ確保判定が行われます。CMake は gfx906 の HIP build ではこのエンジンを追加しません（`engine/src/qwen35/q36_engine.cu:1-3,4337-4348,4470-4478`; `engine/cmake/strata_gpu_engine.cmake:565-571`）。

## 値と判定

`place_experts()` 内で `std::getenv("STRATA_Q36_PEER_VERIFY") != nullptr` を調べます。空文字を含め、変数が存在すれば有効です。文字列比較、数値変換、空白除去、範囲検査はありません。未設定ならこの変数単独では `cpu_chk` を確保しません（`engine/src/qwen35/q36_engine.cu:4476-4477`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CPU pool 対応の Qwen3.6 GPU エンジンが hybrid 配置に進み、別の照合変数が未設定 | `cpu_chk` をこの変数では確保しない | 空文字、`0`、`1`、`true`、その他すべての設定値で確保 | なし（値の内容は検査しない） |

`STRATA_Q36_PEER_VS_C0` も設定されている場合もバッファ確保条件は満たしますが、照合処理はそちらの分岐となり、CPU 対 peer の照合ではなく両 GPU 上の同一 expert 行を照合します（`engine/src/qwen35/q36_engine.cu:3364-3383,4476-4477`）。

## 有効になる条件

- Qwen3.6 GPU エンジン経路であること。このエンジンの実装は `.cu` にあり、HIP gfx906 以外で追加されます（`engine/src/qwen35/q36_engine.cu:1,48-50`; `engine/cmake/strata_gpu_engine.cmake:565-584`）。
- `STRATA_NATIVE_EXPERTS` 有効のビルドであること。これにより `STRATA_Q36_CPU_POOL` が定義されます。無効なら expert が収まらない場合は hybrid 処理へ進まずエラーになります（`engine/cmake/strata_gpu_engine.cmake:574-578`; `engine/src/qwen35/q36_engine.cu:4337-4344`）。
- 全 expert が VRAM に収まらず hybrid 配置へ進むこと。全 expert が収まる早期 return の経路では、この変数を読む箇所に到達しません（`engine/src/qwen35/q36_engine.cu:4318-4337,4345-4350,4476-4477`）。
- peer GPU の行が実際に発生すること。peer tier は `--peer-device` が有効な場合に開かれ、peer 用バッファ確保失敗時は `peer.comp` が null になり CPU pool が全 entry を処理します（`engine/src/qwen35/q36_engine.cu:4077-4079,4203-4235`）。
- 対象レイヤーが通常の hybrid 行経路を通り、peer に該当 expert があり、行数が tier の上限以内であること。大きな prompt chunk は peer tier を通らず、また `had_block != 0` または `gu_nib` のレイヤーも peer share を使いません（`engine/src/qwen35/q36_engine.cu:2902-2924,3191-3209,3312-3315`）。
- `STRATA_Q36_PEER_VS_C0` が未設定なら、この変数が確保したバッファで peer の行を CPU pool でも計算し比較します。同変数が設定されると照合対象は card 0 と peer の両方にある expert に切り替わります（`engine/src/qwen35/q36_engine.cu:3364-3391,4387-4392`）。

## 実行時の詳細

変数は hybrid expert 配置中の `place_experts()` で読み、`T * Kp * N * 4` バイトの CUDA host buffer を `cudaHostAllocDefault` で確保します（`T` は配置時の最大行数、`Kp` は top-k、`N` は埋め込み幅）。関数内の `static` cache はなく、生成・リクエストごとに読み直すのではなく、この配置処理時の値でエンジンの `cpu_chk` の有無が決まります。プロセス実行中に環境を変更しても、既に作られたエンジンのバッファ状態は変わりません（`engine/src/qwen35/q36_engine.cu:4470-4478`）。

peer share が返した各 peer entry について、CPU pool は対象 expert の CPU 計算を追加で行い、その結果を `cpu_chk` に書きます。GPU peer の結果 `cpu_out` と各 float 要素を `!=` で比較し、異なる entry 数と最大絶対差を集計します。CPU 結果は `cpu_out` に置き換えられず、通常どおり peer の結果が merge に渡ります（`engine/src/qwen35/q36_engine.cu:3325-3353,3364-3395`）。

比較は peer entry がある batch ごとに行われます。prompt chunk は peer tier の対象外です。`STRATA_Q36_PEER_VS_C0` が設定されている場合は別分岐で、card 0 と peer の重複 expert の結果を比較します（`engine/src/qwen35/q36_engine.cu:2912-2929,3364-3391`）。

## ログと測定値

差がある場合、または最初の 8 回の比較までは stderr に `strata-q36: peer rows L%zu: %d entries%s, %d differ (max %.3g); total %lld of %lld rows` 形式の行を出します。8 回以降は差がある比較だけ表示します。差がない場合も最初の 8 回までは表示されます。比較差を検出しても、この分岐自体はエラー終了や fallback を行いません（`engine/src/qwen35/q36_engine.cu:3394-3401`）。

照合の性能値はコードおよび参照した `docs/DETAILS.md`、`docs/QWEN36.md` に記載がなく、ここでは示しません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1-3,43-50` — エンジンの用途と CUDA/CPU pool 実装。
- `engine/cmake/strata_gpu_engine.cmake:565-584` — Qwen3.6 GPU エンジンと CPU pool macro のビルド条件。
- `engine/src/qwen35/q36_engine.cu:4318-4348,4470-4478` — VRAM/hybrid 経路、読み取りとバッファ確保。
- `engine/src/qwen35/q36_engine.cu:2902-2929,3191-3209,3312-3353` — peer 対象行と CPU pool の行計算。
- `engine/src/qwen35/q36_engine.cu:3364-3401` — 比較、集計、ログ。
- `engine/src/qwen35/q36_engine.cu:4077-4079,4203-4235,4387-4396` — peer tier の構成・失敗時の扱い・関連照合モード。

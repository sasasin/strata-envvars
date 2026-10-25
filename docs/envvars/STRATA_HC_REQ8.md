# `STRATA_HC_REQ8`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata generate` の単一 GPU 経路で、各層の hyper-connection（HC）`down` / `up` 投影重みを BF16 のまま保持せず、32 要素ごとに FP32 scale を持つ int8 重みに再量子化します。重みの必要 VRAM が減り、その分を expert cache に回せます。実装コメントは元の BF16 と出力が変わる opt-in 機能としています（`src/program/generate.cpp:3591-3599`）。

## 値と判定

値は `std::atoi()` で整数に変換し、結果が 0 以外なら要求 ON、0 なら OFF です。文字列全体の妥当性は検査しません。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字、`0`、`00`, `abc`、`0abc` | OFF（`atoi` の結果が 0） |
| `1`, `-1`, `2`, `1tail`, ` 1` | ON（先頭の整数変換結果が 0 以外） |
| `0x1` | OFF（10 進整数として先頭の `0` を変換） |

整数の後ろに文字があっても、変換できた先頭部分で判定します。値の大文字小文字は関係ありません。CLI オプションによる同じ機能の明示的な設定や、別環境変数との優先順位はありません。環境は `generate` のこの初期化箇所で読み取られ、同一の値を起動中に再評価する処理はありません（`src/program/generate.cpp:3594`）。

## 有効になる条件

- `STRATA_HC_REQ8` が ON で、layer split ではないこと。複数 GPU のときは `STRATA_HC_REQ8 does not support a layer split yet - the BF16 projections are used` という警告を出し、量子化を行いません（`src/program/generate.cpp:3595-3599`）。
- パック内の HC down/up テンソルが BF16 で、各テンソルの `ne0` が 32 の倍数であること。パック側の source bytes は要素数の 2 倍（raw BF16）または 4 倍（F32 に格納された BF16）でなければなりません。条件外なら `load_hc_q8()` がエラーを返し、generate は終了します（`src/core/weights.cpp:525-538`, `src/program/generate.cpp:3649-3652`）。
- 量子化後の重みを token 経路で使うには、fused HC read が実際に選ばれること。generate は `--gr-native-mmvf` が有効で、`--no-fused-gr`、`--gpu-stages`、layer/half dump、`--stage-timing` がなく、さらにモデル形状が fused kernel の対応形状である場合に fused read を設定します。`--native` は `gr_native_mmvf` を有効にします（`src/program/generate.cpp:3033-3037,3678-3679`; `src/core/layer.cpp:1399-1400`; `src/kernels/cuda/fused_gr.cu:2363-2365`）。

## 実行時の詳細

有効かつ単一 GPU の場合、generate は全層の `hc_attn_{down,up}.weight` と `hc_ffn_{down,up}.weight` を通常の weight arena から除外し、パックから読み直して量子化します。各連続 32 要素について `amax = max(abs(x))`、scale `d = amax / 127`、コード `nearbyint(x / d)` を計算します。`amax` が 0 のブロックでは逆 scale とコードは 0 です。int8 コードと各ブロックの FP32 scale を GPU に割り当て、WeightRef に記録します。対象テンソルがなければ変換対象が空なので成功し、アップロード量 0 のログになります（`src/core/weights.cpp:518-599`）。

decode の fused HC kernel は scale の有無で BF16/int8 の読み方を分け、int8 重みと scale を使います（`src/core/layer.cpp:1458-1465,1481-1489`; `src/kernels/cuda/fused_gr.cu:1232-1235,1295-1305,1328-1337,2374-2380`）。prefill の BF16 GEMM 経路では、int8 重みを再利用 scratch に一時的に BF16 展開してから GEMM に渡します（`src/prefill/prefill.cpp:2258-2279`）。

有効な変数を設定しても fused read が選ばれない場合、decode の非 fused 経路は `STRATA_HC_REQ8 needs the fused hyper-connection read` を返します（`src/core/layer.cpp:1465-1466,1488-1489`）。したがって `--no-fused-gr` など fused 設定を無効にするオプションとの併用は、BF16 に自動 fallback する動作ではありません。multi-GPU では上記の明示的な警告と BF16 fallback が別途実装されています。

## 文書との照合

`docs/DETAILS.md:2236` はこの変数を「32 ごとの scale を持つ int8 HC 投影」と記載し、丸め誤差レベル（KL 0.0018）、decode の性能を RTX 3060 / A4000 の列で `-0.2% / +2.2%` と要約しています。同じ表のこの行には測定条件の詳細がないため、この数値を他の構成へ一般化しません。実装コメントも出力が変わるとしています。

## 根拠

- 読み取り、split fallback、読み込み前の除外指定、ロードとログ: `src/program/generate.cpp:3591-3599,3644-3657`。
- 対象名と BF16 → int8 量子化・GPU 格納: `src/core/weights.cpp:518-599`。
- token 経路の fused 条件・非 fused エラー: `src/core/layer.cpp:1399-1400,1458-1466,1481-1489`。
- CUDA fused kernel の Q8 分岐と形状条件: `src/kernels/cuda/fused_gr.cu:1232-1235,1295-1305,1328-1337,2363-2380`。
- prefill の BF16 展開: `src/prefill/prefill.cpp:2258-2279,2958-2974`。
- 関連資料: `docs/DETAILS.md:2236`。

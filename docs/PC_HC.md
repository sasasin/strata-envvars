# `PC_HC`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal のテスト／計測プログラム `prompt_chain` が prompt 中の hyper-connection (HC) read に使う dispatch 経路を選びます。これは Strata の `strata` エンジン本体の設定ではありません。`metal/tests/prompt_chain.cpp` が環境変数を読み、HC read を fused 経路または複数 dispatch の plain 経路として組み立てます。

## 値と判定

値は文字列全体で比較され、数値変換や真偽値 parse はありません。

| `PC_HC` の状態 | `hc_mode` | HC read の経路 |
|---|---|---|
| 未設定 | `fused` | fused |
| `fused` と完全一致 | `fused` | fused |
| 空文字 | 空文字 | plain |
| `fused` 以外の設定値（例: `plain`, `FUSED`, `0`, `1`） | 設定値そのまま | plain |

比較は大文字小文字を区別します。設定値の妥当性検査や警告はありません。したがって、`plain` 専用の値が強制されるわけではなく、`fused` 以外はすべて plain 側の `else` 経路になります。

## 有効になる条件

この変数を読むのは `metal/tests/prompt_chain.cpp` だけです。同ファイルは `metal/CMakeLists.txt` の `metal/tests/*.cpp` glob から実行ファイル `prompt_chain` としてビルドされます。Metal の CMake プロジェクトは `APPLE` 以外では構成を停止するため、このプログラムは macOS 向けです。Strata の通常の `strata` エンジンや他 backend の動作には影響しません。

## 実行時の詳細

`main()` で `std::getenv("PC_HC")` を一度呼び、未設定の場合だけ既定文字列 `fused` を設定します。値はプロセス内の `hc_mode` に保持され、以後の HC read に使われます。実行中に環境を変更して再評価するコードはありません。

各 layer の attention HC read と FFN HC read は `hc_read()` を通り、`hc_mode == "fused"` の場合は `gr_norm_h`、down projection、`gr_epi_down`、mixing epilogue 付き `gemm_hc_up_64_64_4` を dispatch します。それ以外は `gr_norm`、`act_f16`、down projection、`gr_epi_down`、up projection、`gr_epi_up` の plain dispatch 群を使います。従って選択は warm-up と計測対象の prompt chunks にも同じく適用されます。

prompt の最後に LM head 用として行う最終 HC read は `hc_read()` を使わず、`gr_norm` / `gr_down` / `gr_up` の decode dispatch を直接構築するため、`PC_HC` の分岐対象ではありません。`PC_HC` 専用のログ出力も見つかりません。

## 根拠

- `metal/tests/prompt_chain.cpp:127-128`: 環境変数の読み取り、未設定時の `fused` 既定値。
- `metal/tests/prompt_chain.cpp:249-281`: `hc_read()` の fused / plain dispatch 分岐。
- `metal/tests/prompt_chain.cpp:283-400`: layer ごとの attention / FFN HC read 呼び出し。
- `metal/tests/prompt_chain.cpp:466-488`: `hc_read()` を介さない最終 HC read と LM head。
- `metal/CMakeLists.txt:16-18,41-47`: macOS 制約と `metal/tests/*.cpp` からの実行ファイル生成。
- `docs/DETAILS.md`: `PC_HC` の説明は見つからず、照合できる設計説明・測定値はない。

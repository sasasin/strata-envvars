# `STRATA_Q36_OLD_KERNELS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部ライブラリや GPU ドライバーが読む環境変数の動作は含めない。

## 役割

Qwen3.6-35B-A3B 用の `strata-q36` エンジンで、Q36 専用の高速カーネル経路を使うかを選びます。未設定なら高速経路を使い、設定されていれば従来経路を選びます。従来経路に切り替えるための診断・比較用フックです。

これは `strata` の通常モデル経路全体や、全ての最適化を無効にするスイッチではありません。対象エンジン内で `fast_k` を参照する分岐だけに作用します。

## 値と判定

| 環境変数の状態 | `fast_k` | 動作 |
|---|---:|---|
| 未設定 | `true` | 条件を満たす箇所でQ36専用高速カーネルを使用 |
| 設定あり（空文字を含む） | `false` | `fast_k` に依存する箇所で従来経路を選択 |

値は文字列として比較せず、数値変換もしません。`=1` だけでなく `=0`、`=false`、空文字など、何らかの値が設定されていれば同じく `fast_k=false` です。実装は `std::getenv(...) == nullptr` の結果を `Engine` のメンバー初期化時に bool として保持します。エンジン稼働中に環境を変更しても、そのインスタンスの判定は変わりません。

## 有効になる条件

Qwen3.6 エンジンのコードがビルドされている CUDA または HIP 構成で、`strata` が `qwen35moe` モデルを同エンジンに渡す場合、または専用実行ファイル `strata-q36` を使う場合に関係します。CPU のみの構成では GPU バックエンドとともにこのエンジンはビルドされません。

環境変数が未設定でも、各高速カーネルは形状やデータ形式などの個別条件を満たす場合だけ使われます。例えば、Q8_0 の小規模行列積は列数 1–8、入力次元の 32 倍数、最大 64 ブロックなどの条件があり、共有 expert の fused 経路は列数 1–4 と形状・Q8_0 条件を要します。router と grouping の fused 経路は列数 8 以下、expert 数 256、top-k 8 が条件です。これらの条件を満たさない場合は、変数が未設定でも既存の経路に進みます。

`STRATA_Q36_VERIFY` は別の環境変数です。これを設定すると有効な高速経路の出力を従来経路と照合するコードが働きますが、`STRATA_Q36_OLD_KERNELS` 自体の判定を変更するものではありません。`STRATA_Q36_NO_EXT` も router/shared gate の一部融合条件に関係します。

## 実行時の詳細

`fast_k` は Q36 `Engine` インスタンスが作られるときに一度だけ決まります。主な適用箇所は次のとおりです。

- decode の小さな Q8_0 行列積で専用の `q8_rows` kernel を使うか（該当しない場合は native MMVQ）。
- add + RMS norm + Q8_1 量子化の fused kernel、共有 expert の gate/up/SwiGLU/量子化の fused kernel、router/top-k/grouping の fused kernel、小さい routed-entry grouping と MoE 終端処理の fused kernelを使うか。
- prompt の GDN convolution を 16-token 単位の tile に分けるか。GDN の別の列分割経路など、`fast_k` に依存しない処理まで一括して無効にはしません。
- 複数行で router と shared-expert gate を一つの積にまとめる経路を使うか。1行 (`T == 1`) は `one` 条件が優先され、この変数の設定有無にかかわらずその積の経路を使います。
- MTP draft head で先頭 `draft_n` 語彙だけを処理する専用 kernel を使うか。`fast_k` が false、または語彙数・行列形式・次元などの条件を満たさない場合は、通常の全語彙 `head_rows` に戻ります。

この変数専用の警告や状態ログはありません。通常経路への切り替えは `fast_k` を調べる分岐で行われ、設定値自体は出力されません。プロジェクトの `docs/QWEN36.md` は `STRATA_Q36_OLD_KERNELS=1` を新しい decode / prompt kernel 群を切る方法として記載しています。上記の適用範囲と条件は HEAD の実装を優先して記述しています。

## 根拠

- `src/qwen35/q36_engine.cu:1575-1578` — `fast_k` は環境変数が未設定かどうかだけで初期化。隣接する `verify_k` は別スイッチ。
- `src/qwen35/q36_engine.cu:1599-1625,1672-1693,1695-1732` — 小型 Q8_0、add/RMS/量子化、共有 expert の高速経路と各条件。
- `src/qwen35/q36_engine.cu:1791-1832,1837-1862` — router/grouping と MoE 終端の高速経路、形状条件。
- `src/qwen35/q36_engine.cu:1912-1921,1998-2005,2104-2128` — prompt GDN tile、router の積の条件、MTP draft head と fallback。
- `CMakeLists.txt:315-316,711-725` — GPU backend 条件下での Qwen3.6 エンジンのビルドと `strata` / `strata-q36` への接続。
- `docs/QWEN36.md:128-134` — プロジェクト資料の高速カーネル、照合設定、およびこの環境変数の説明。

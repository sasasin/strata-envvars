# `STRATA_METAL_PROMPT_HOSTPIPE`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal の prompt-chain 経路で、次の prompt chunk 用の token embedding 行と PLE table 行を CPU 側で先行計算し、現在の chunk の GPU 処理と重ねます。無効にすると、次 chunk の host 行はその chunk を処理する `pc_chunk()` 内で計算されます。これは prompt 処理のスケジューリングを変える設定で、計算内容自体を変える分岐ではありません。

## 値と判定

`Window::pc_chunk()` 内の関数ローカル `static const bool` が `std::getenv()` の値を文字列全体で比較します。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効 |
| 値が厳密に `0` | 無効 |
| その他の設定値（`00`、`false`、`0 `、`1` など） | 有効 |

数値変換、trim、大文字小文字変換、範囲制限はありません。無効値を知らせる警告や fallback 用の別値はありません。CLI 引数や別の環境変数がこの値を上書きする処理も見つかりません。

## 有効になる条件

値判定が有効でも、次の条件が必要です。

- `prompt_run_rows()` が Metal decode window を初期化済みである。
- `STRATA_METAL_PROMPT=window` が選ばれておらず、streaming 経路でもない。
- prompt の行数 `n` が `STRATA_METAL_PROMPT_MIN` 以上（既定 32）であり、`Window::prompt()` の prompt-chain 経路に入る。
- 現在処理中の chunk の後に次 chunk がある（`next_tokens != nullptr` かつ `next_nT > 0`）。最終 chunk のための先行計算は開始しない。
- 呼び出し側の embedding 行がない（`g_embd_rows == nullptr`）。呼び出し側の行がある場合、この先行計算分岐は使われない。

この条件外では、この変数による先行計算は行われません。`STRATA_METAL_PROMPT=window`、prompt 長による経路選択、streaming 時の別経路は `metal/src/engine/window.cpp:3593-3625` にあります。

## 実行時の詳細

値は `pc_chunk()` が初めてこの判定箇所に到達したときに読み込まれ、`static const` に保存されます。同一プロセスで以後の呼び出しは保存値を使うため、初回評価後に環境を書き換えても再評価されません。prompt-chain 自体を使わないプロセス経路では、この判定箇所に到達しません。

先行計算が有効な場合、現在 chunk の GPU dispatch を実行する前に `std::async(std::launch::async, ...)` で次 chunk の `pc_host_rows()` を起動します。host 側ではモデルファイルの token embedding を dequantize し、PLE が有効なら n-gram 行を作って table から gather します。次の `pc_chunk()` は future の結果を取得して行を使います。先行計算結果が失敗または chunk 座標・行数と一致しない場合は、現在 chunk の host 行をその場で再計算します。同期再計算も失敗した場合はエラー文字列を返して prompt を失敗させます。

この変数専用のログ・警告・終了経路はありません。`STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されていると、stderr に prompt 全体の GPU 時間、host rows 時間、GPU と重なった host rows 時間などを含む集計ログが出ます。これはこの変数の値を直接表示するログではありません。

## 根拠

- `metal/src/engine/prompt_chain.inc:526-537`: 値の取得・保存、次 chunk と caller embeddings の条件、非同期 host 行計算の起動、現在 chunk の GPU 実行。
- `metal/src/engine/prompt_chain.inc:189-217`: host 行計算が行う embedding dequantize と任意の PLE 行生成、gather の成否。
- `metal/src/engine/prompt_chain.inc:220-239`: 次 chunk の非同期結果取得と不一致・失敗時の同期再計算。
- `metal/src/engine/prompt_chain.inc:564-593`: prompt の chunk ループ、prompt 長や context 境界の失敗、trace/profile 時の集計ログ。
- `metal/src/engine/window.cpp:3593-3625`: Metal prompt の経路選択と window fallback。

候補名の全参照を検索した結果、値を読むのは `metal/src/engine/prompt_chain.inc:526` のみです。`metal/src/engine/window.cpp:628` にも名前がありますが、これは無効時の動作を説明するコメントです。

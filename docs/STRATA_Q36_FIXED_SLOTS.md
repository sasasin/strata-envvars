# `STRATA_Q36_FIXED_SLOTS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6 engine の hybrid expert 配置で、実行中に行う VRAM slot の専門家入れ替えを止めます。起動時に配置された slot はそのままになり、ルーティング頻度に応じた再配置は行われません。コードコメントではテスト用のフックとされています。

対象は `src/qwen35/q36_engine.cu` の Qwen3.6 engine です。`strata-q36` と、`qwen35moe` モデルをこの engine に渡す `strata` の経路で使われます。通常の全専門家 VRAM 常駐経路ではなく、hybrid 配置が必要です。

## 値と判定

値そのものは parse せず、`std::getenv(...) != nullptr` で設定有無だけを判定します。

| 状態 | 入れ替え |
|---|---|
| 未設定 | 有効（他の条件を満たす場合） |
| `1`、`0`、`false`、任意の文字列 | 無効 |
| 空文字（設定済み） | 無効 |

したがって `STRATA_Q36_FIXED_SLOTS=0` も入れ替えを停止します。文字列の大小文字、数値変換、範囲検査はありません。CLI オプションや設定ファイルによる上書きもありません。

## 有効になる条件

- hybrid expert 配置が使われること。たとえば `--expert-slots` で slot 数を指定するか、全 routed expert が VRAM に収まらず hybrid になる場合です。
- hybrid を使うビルドでは CPU expert pool が必要です。`STRATA_NATIVE_EXPERTS` が無効で VRAM に収まらない場合、配置処理はエラーを返すため、この環境変数による slot 入れ替え制御には到達しません。
- 全専門家が VRAM に置かれる場合、通常の呼び出し経路は `rebalance()` を呼ばないため、この変数は効果を持ちません。

環境変数は初期配置を決めません。hybrid 配置時は各対象 layer の slot `0..S-1` に同じ番号の expert を初期配置します。この初期割り当てを維持するのがこの変数の効果です。

## 実行時の詳細

`rebalance()` は、decode/verify で確定した行を数えた後、位置が32の倍数になると呼ばれます。また prompt 処理の最後にも呼ばれます。通常の hybrid 経路では、`rebalance()` は環境変数を関数内 `static const bool` に一度だけ読み込み、未設定でなければ直ちに戻ります。値の確認、ログ出力、警告はありません。最初の `rebalance()` 後にプロセス環境を変更しても判定は変わりません。

この変数が未設定の場合、各 layer の利用スコア上位 `S` expert を slot に置くように候補を選び、最大 `max_swaps` 件まで host から VRAM にコピーして slot 対応表を更新します。decode 境界では一度に最大8件、prompt 後は既定で最大2048件です。固定 slot 時はこれらのコピーと対応表更新が行われず、レポートの `slot replacements` は増えません。expert の計算が GPU/CPU のどちらに割り当たるかは、固定配置のままルーティング結果に応じて決まります。

通常の warm-up は hybrid prompt を処理し、その終端の `rebalance()` でこの static 判定を初期化します。`--no-warmup` の場合は、最初の prompt 終端またはdecode/verifyの32位置境界で初期化されます。

## 根拠

- `src/qwen35/q36_engine.cu:1700-1749` — 設定有無の判定、固定時の早期 return、スコアに基づく入れ替え、コピー、slot 対応表の更新。
- `src/qwen35/q36_engine.cu:1115-1133,1798-1822` — decode/verify 境界と prompt 終端からの呼び出し条件、頻度と swap 上限。
- `src/qwen35/q36_engine.cu:2025-2037,2056-2090` — CPU pool を使う hybrid 経路、slot 数決定と初期配置。
- `src/qwen35/q36_engine.cu:1890-1915,2346-2352,2373-2377` — 既定 warm-up と `--no-warmup`。
- `CMakeLists.txt:631-645` — `strata-q36` と `strata` に engine を組み込み、`STRATA_NATIVE_EXPERTS` 有効時に CPU pool をリンクする構成。
- ソース全体での完全一致検索では参照は上記1箇所だけです。`docs/DETAILS.md` などの資料に、この環境変数を説明する記述は確認できませんでした。

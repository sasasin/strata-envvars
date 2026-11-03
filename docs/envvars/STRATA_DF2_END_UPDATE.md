# `STRATA_DF2_END_UPDATE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーの DFlash2 生成で、EOS または出力上限に達してリクエストが終わる window の確定行を、DFlash2 の context ring に反映します。これにより、次のリクエストが前の会話を再開したとき、DFlash2 の ring に確定行の位置が欠ける状態を避けます。値を読むのは `src/program/generate.cpp` のサーバー処理だけです。`strata generate` の通常の生成ループにはこの判定はありません。

## 値と判定

数値変換や文字列全体の parse はしません。`getenv()` が返す文字列の先頭文字だけで判定します。

| 値 | 判定 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 有効（設定済みだが先頭文字は `\0`） |
| 先頭文字が `0` | 無効。`0` や `0anything` を含む |
| それ以外 | 有効。例: `1`、`false`、空白で始まる文字列 |

大文字小文字、数値としての妥当性、後続文字は判定しません。CLI 引数や別の環境変数による値の上書きはありません。

## 有効になる条件

この処理がコンパイルされるのは、CMake で CUDA または HIP を有効にし、`STRATA_HAVE_DFLASH2` が定義されるビルドです。Metal と SYCL のビルドでは DFlash2 自体を含めません（`CMakeLists.txt:429-436`）。

実行時には、次の条件がすべて必要です。

- サーバーの生成 window を処理している。
- DFlash2 がロード・準備され、`use_df2` が真である。
- このリクエストで DFlash2 を使う（`req_df2` が真）。`--draft auto` の場合はリクエスト単位で選択されます。
- 最初の prompt と生成をまとめた window ではない（`merged` が偽）。
- この window で EOS token が出たか、生成数が `max_new` に達した。

DFlash2 の初期化に失敗して MTP へ fallback した場合、この更新は行われません。値が有効でも、以上の条件を満たさない通常の継続 window では追加更新しません。

## 実行時の詳細

判定結果は関数内の `static const bool` に一度だけ保存されます。サーバープロセスが生成 window 後の判定箇所へ初めて到達したとき評価され、その後に環境を変更しても同じプロセスでは再評価されません。DFlash2 を使わない最初の request でも、この判定箇所に到達すれば値は cache されます（`src/program/generate.cpp:18576-18580`）。

条件を満たすと、直前に確定した `a + 1` 行の taps を取得し、位置 `p` から `df2.context()` に渡します。単一 GPU では verifier の tap buffer を使い、layer split では各 stage の taps を DFlash2 の landing buffer に集めます（`src/program/generate.cpp:11178-11183,18580-18582`）。`Dflash2Drafter::context()` は待機中の context 更新を完了させ、行ごとの位置 metadata を設定して context kernel を記録・実行し、CUDA stream を同期してから ring の有効範囲を進めます（`src/core/dflash2.cpp:968-985`）。

更新に失敗すると stderr ではなく stdout に `ERR <理由>` を出して、このサーバー処理をエラー終了します。stage taps の収集失敗、context kernel の記録失敗、CUDA stream 同期失敗がこの経路に含まれます。成功時にこの環境変数専用のログはありません（`src/program/generate.cpp:18580-18582`; `src/core/dflash2.cpp:968-985`）。

## 根拠

- 候補名の全参照は `src/program/generate.cpp:18579` の直接読み取り 1 箇所です。読み取り API や動的な env helper を介した別の参照は見つかりませんでした。
- 環境変数の判定と適用条件: `src/program/generate.cpp:18576-18583`。
- サーバーでの DFlash2 初期化、fallback、request 内の DFlash2 選択: `src/program/generate.cpp:11146-11175,15190-15234`。
- taps の単一 GPU / layer split 経路: `src/program/generate.cpp:11178-11183`。
- context ring の更新と失敗条件: `src/core/dflash2.cpp:968-985`。
- DFlash2 を含む build 条件: `CMakeLists.txt:429-436`。
- `docs/DETAILS.md` にこの環境変数の説明や測定値は見つかりませんでした。`docs/envvars/000_envvers.md` の候補名は、上記の読み取り実装で実在を確認しました。

# `STRATA_METAL_TRACE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal エンジンのデコード window と prompt の処理時間・出力 token の診断行を stderr に出します。計算方法や token 選択を切り替える分岐ではなく、ログ出力だけを制御します。対象は `metal/src/engine/` の Metal 実装で、CUDA/HIP/SYCL の実装からはこの名前を読み取るコードは見つかりませんでした。

## 値と判定

値の parse はありません。3か所とも `std::getenv("STRATA_METAL_TRACE")` のポインターが null かどうかで判定するため、未設定なら無効、設定されていれば値を問わず有効です。

| 環境の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| `1`、`0`、`false`、その他の文字列 | 有効 |
| 空文字（`STRATA_METAL_TRACE=`） | 有効 |

文字列全体・先頭文字・大文字小文字・数値としての妥当性はいずれも検査しません。CLI や設定ファイルによる上書きは、この変数の読み取り箇所にはありません。

## 有効になる条件

Metal エンジンの該当経路が実行されることが条件です。リポジトリの Mac 向け説明では、エンジンの実装は `metal/` にあり、`STRATA_METAL_TRACE=1` はテスト用スイッチとして案内されています（`docs/MAC.md:183-205`）。ビルド設定で Metal エンジン自体が無効、または利用可能な Metal エンジンを通らない場合、このログは出ません。

プロンプト全体の集計行は `STRATA_METAL_PROFILE` が設定されている場合にも出ます。そのため `STRATA_METAL_TRACE` が未設定でも、`STRATA_METAL_PROFILE` が設定され、prompt chain の処理が通れば集計行は出ます。この条件は window 単位の trace 行には適用されません。

## 実行時の詳細

- `Window::finish()` は最初の呼び出しで `STRATA_METAL_TRACE` の有無を `static const bool` に保存します。有効で、その window が `head` を持つ場合、stderr に位置、入力 token、出力 token、logits 上位2候補と margin、window の経過時間・GPU 時間・dispatch 数を出します。`head` がない window ではこの行を出しません（`metal/src/engine/window.cpp:1319-1348`）。
- `Window::pc_chunk()` も最初の呼び出しで値の有無を static に保存します。有効なら各 prompt chunk の位置、行数、実行時間を stderr に出します（`metal/src/engine/window.cpp:2413-2426`）。
- prompt chain の処理後には、各呼び出しで `STRATA_METAL_TRACE` と `STRATA_METAL_PROFILE` の有無を調べます。どちらかが設定されていれば、prompt token 数、総時間、GPU 時間、host row 時間、drafter row 時間、token/s の集計行を stderr に出します（`metal/src/engine/prompt_chain.inc:400-420`）。

最初の2経路は環境変数を初回に読むため、その後プロセス内で環境を変更しても当該経路の判定は変わりません。prompt chain の集計行は毎回 `getenv()` を呼ぶため、呼び出し時点の値を判定します。これらの読み取りは処理結果を変更しません。

## 根拠

- 全リポジトリの名前検索で確認した読み取り箇所: `metal/src/engine/window.cpp:1336,2424`、`metal/src/engine/prompt_chain.inc:416`。
- decode trace の出力と `head` 条件: `metal/src/engine/window.cpp:1336-1347`。
- prompt chunk trace: `metal/src/engine/window.cpp:2413-2426`。
- prompt 全体の集計と `STRATA_METAL_PROFILE` との OR 条件: `metal/src/engine/prompt_chain.inc:400-420`。
- Mac 向け資料のスイッチ一覧と Metal 実装の説明: `docs/MAC.md:183-205`。資料の表は trace の概要を示していますが、空文字・`0` も有効となる判定規則はソースに基づきます。

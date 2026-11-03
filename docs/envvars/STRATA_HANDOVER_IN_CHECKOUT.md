# `STRATA_HANDOVER_IN_CHECKOUT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。作業開始時の Strata status は `## main...origin/main` で、未コミット変更は表示されませんでした。

## 役割

通常、ソース checkout から起動した `strata.py` は、インストール済み Control への hand-over を試しません。この変数に空でない値を設定すると、その checkout 判定を通過させ、`strata update` が配置した新しい Control への hand-over 判定を続けます。これは hand-over 自体を強制する設定ではなく、checkout からの実行を止める条件だけを解除します。実際の entry point は `strata.py` の起動時、CLI の heavy import とコマンド処理の前に hand-over 関数を呼びます（`strata.py:30-43`、`strata_cli/handover.py:126-150`）。

## 値と判定

数値や文字列の parse はありません。`maybe_hand_over()` は `environ.get(ENV_CHECKOUT)` を Python の真偽値として判定します。通常の entry point では `environ` に `os.environ` が使われます（`strata_cli/handover.py:24,126,129-133`）。

| 環境の状態 | checkout 判定への効果 |
|---|---|
| 未設定 | 偽。checkout 上なら hand-over 判定を止める |
| 空文字 (`STRATA_HANDOVER_IN_CHECKOUT=`) | 偽。未設定と同じ |
| 空でない値（例: `1`, `0`, `false`, `anything`） | 真。checkout 判定を通過する |

したがって `0` や `false` も無効化値ではなく、空でなければ checkout 判定を通過させます。大文字小文字、空白、数値としての妥当性は検査されません。

## 有効になる条件

この変数の判定に到達するには、先行する `STRATA_HANDOVER` と `STRATA_NO_HANDOVER` の両方が未設定または空文字である必要があります。どちらかに空でない値があると hand-over 関数は直ちに `None` を返します（`strata_cli/handover.py:129-133`）。

値が空でない場合でも、`root` 引数が明示されている呼び出しでは checkout 判定自体を通りません。また、`root` が省略されていても `running_from_checkout()` が偽なら、この変数による効果はありません。同関数は `strata_cli/handover.py` の実体位置から二階層上に `.git` が存在するかで checkout を判定します（`strata_cli/handover.py:27-29,132`）。

checkout 判定を通過した後も、現在の Control の version が読めない、active pointer が使えない、新しい Control が見つからない、対象 Control が不完全、といった条件によって hand-over は行われないことがあります。新しい対象が有効である場合に限り、その Control の Python と `strata.py` を使って現在の引数を引き継ぎます（`strata_cli/handover.py:134-150`）。この環境変数に CLI 引数や別設定を上書きする処理はありません。

## 実行時の詳細

値は `maybe_hand_over()` の呼び出しごとに `environ.get()` で読み、static cache はありません。通常の実行経路では `strata.py` 起動時に一度呼ばれるため、その呼び出し時点の `os.environ` が判定に使われます。関数呼び出し後にプロセス環境を書き換えても、その判定結果が再評価される箇所はありません（`strata.py:30-38`、`strata_cli/handover.py:126,129-133`）。

新しい Control を起動する環境は元の環境のコピーです。従ってこの変数も子プロセス環境に残りますが、同時に `STRATA_HANDOVER=1` が設定されるため、次の起動では hand-over の先行ガードが優先され、ループを防ぎます（`strata_cli/handover.py:117-123,129-133,148-158`）。POSIX では `execve` でプロセスを置き換え、Windows では subprocess の終了コードを返します（`strata_cli/handover.py:151-162`）。

この変数が空でないこと自体によるログや終了コードはありません。checkout 判定を通過した後、対象 Control に問題がある場合は stderr に修復案内の警告を出し、現行 Control の実行を続けます。起動に失敗した場合も stderr に警告を出して現行 Control を続行します（`strata_cli/handover.py:137-145,151-163`）。

## 根拠

- 候補名の定義と唯一の本番読み取り、および checkout 条件: `strata_cli/handover.py:22-29,126-145`。
- 起動時の呼び出し位置と呼び出し後の通常 CLI への続行: `strata.py:30-43`。
- hand-over 環境のコピー・guard 設定と OS 別起動経路: `strata_cli/handover.py:117-123,148-163`。


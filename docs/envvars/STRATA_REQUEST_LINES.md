# `STRATA_REQUEST_LINES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`terminal/serve` の Python サーバーが、エンジンのログファイルからリクエスト完了行を読み取り、サーバープロセスの stdout に `[strata] request ...` 行として再出力するための設定です。リクエスト処理や生成の選択・計算は変えず、エンジンの stderr がログに送られる構成でも、サーバー外側の supervisor がリクエスト単位の数値を stdout で観測できるようにします（`terminal/serve/server.py:533-553, 809-835`）。

## 値と判定

サーバー側の `os.environ.get("STRATA_REQUEST_LINES")` の戻り値を Python の真偽値として判定します。文字列を `1` や真偽値として parse しません（`terminal/serve/server.py:809`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の `StrataEngine` 初期化 | 無効 | 空文字列でない任意の値。`1`、`true`、`false`、`0`、`0anything`、空白だけの値も有効 | 未設定、明示的な空文字列 |
| `lazy=True` の初期化 | ログ追従処理自体を開始しない | なし | 値にかかわらず適用されない |

大文字小文字、前後の空白、数値としての妥当性は検査されません。たとえば `false` や `0` も空でない文字列なので有効です。変数の値による fallback や範囲制限はありません（`terminal/serve/server.py:798-811`）。

## 有効になる条件

- 対象は `terminal/serve` のサーバープロセスです。エンジン単体の起動時にこの変数を読む箇所はなく、候補名の全参照ではサーバーの設定有無チェックだけが実読み取りです（`terminal/serve/server.py:809`）。
- `StrataEngine` が lazy 初期化ではなく、かつ `log` パスを受け取る必要があります。ログがない場合はエンジン stderr が `DEVNULL` に向けられ、この追従スレッドも作られません（`terminal/serve/server.py:798-811, 833-835`）。
- 1 つの絶対ログパスにつき追従スレッドを一度だけ作成します。同じログを使うエンジン再起動では既存スレッドが追従を続けるため、再初期化のたびに別のスレッドは作られません（`terminal/serve/server.py:808-811`; `_echoing` は `terminal/serve/server_parts/engines.py:185`）。
- CLI 引数や設定ファイルによる値の上書き・優先順位はありません。サーバープロセス自身の環境を直接確認します。エンジン起動用の `env` 引数は別に渡されており、この分岐はそれを参照しません（`terminal/serve/server.py:809, 833-835`）。

## 実行時の詳細

`StrataEngine.__init__` は lazy 判定の後、指定されたログの現在のサイズを基準位置として記録します。変数が有効なら、ログの絶対パスが `_echoing` に未登録の場合に限り、デーモンスレッドで `echo_requests(log, 現在のサイズ)` を開始します。追従関数はその位置からログを開いて行単位で読み、まだ新しい行がない場合は 0.2 秒待って再試行します（`terminal/serve/server.py:798-811, 533-553`）。

この変数はエンジン起動前のサーバー側で評価され、エンジンの環境変数として値を転送する処理ではありません。値を設定・変更しても、既に追従中のログには再評価が行われません。同じサーバープロセス内で新たなログパスを初期化した場合は、その時点の環境値と `_echoing` の登録状態で判定されます（`terminal/serve/server.py:809-811`）。

追従側は `ENGINE_REQUEST` 正規表現に一致したログ行だけを出力します。正規表現は prompt token 数、再利用数、読み取り時間と速度、生成数、生成時間と速度を拾い、`echo_requests` は `cached` を再利用数、`total` を読み取り時間と生成時間の合計として表示します。プロンプト読込途中のキャンセル形式（`<read> of <total> read`）も一致対象です（`terminal/serve/server_parts/engines.py:178-182`; `terminal/serve/server.py:548-553`）。Strata エンジンの標準サーバー経路は完了時に同じ項目を stderr に書きます（`engine/src/program/generate.cpp:23754-23765`）。

## ログと測定値

追従スレッドが一致行を見つけると、stdout に次の形式を flush 付きで出します（実際の数値・速度部分はログから取得）。

```text
[strata] request prompt P cached C output O prompt_read R ms total S ms prefill X tok/s decode Y tok/s
```

出力文字列は `terminal/serve/server.py:551-553`、元のエンジン側の完了行は stderr への `strata serve: prompt ...` 出力として `engine/src/program/generate.cpp:23760-23765` にあります。エンジン側ログ行が正規表現に一致しない場合、この機能による stdout 行は出ません。測定値や性能差を示す資料はこの設定の根拠として確認できなかったため記載していません。

## 根拠

- `terminal/serve/server.py:533-553` — ログ追従、行の正規表現照合、stdout 出力。
- `terminal/serve/server.py:798-811` — lazy 判定、ログの有無、環境値の読み取り、ログごとの追従スレッド制御。
- `terminal/serve/server.py:833-835` — エンジン stderr をログへ、stdout をパイプへ接続する起動経路。
- `terminal/serve/server_parts/engines.py:178-185` — 対象となるエンジン行の正規表現と既追従ログ集合。
- `engine/src/program/generate.cpp:23754-23765` — 通常の Strata サーバー経路が出すリクエスト完了行。

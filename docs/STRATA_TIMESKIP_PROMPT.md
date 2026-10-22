# `STRATA_TIMESKIP_PROMPT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Time-skip の各修正試行で、修正コマンドに渡す「何を変更するか」の指示文です。通常は `strata timeskip run --prompt ...` の引数が元になり、CLI が修正コマンドの子プロセス環境へ `STRATA_TIMESKIP_PROMPT` として設定します。単独で環境変数を設定しても、Time-skip の開始や試行は起きません。

アプリの Time-skip 経路では、ホストが同じ値を CLI の `--prompt` 引数に渡し、既定の修正スクリプト `apps/host/server/timeskip-revise.mjs` が環境から読み取ってホスト内の revision API に送ります。CLI の組み込み Harness 連携 `integrations/harness/revise_once.py` も、`--revise-command` に指定して使う場合の読み取り先です。

アプリの `/api/timeskip/start` はリクエストの `prompt` を文字列化し、前後の空白を除いてから 4,000 文字で切り詰めて CLI に渡します。この上限はアプリの入力経路にある制限で、環境変数を直接消費する両スクリプトに共通の上限ではありません。

## 値と判定

この環境変数自体に真偽値・数値の parse はありません。値は指示文として扱われます。

| 読み取り箇所 | 未設定 | 空文字・空白だけ | その他 |
|---|---|---|---|
| `integrations/harness/revise_once.py` | 空文字相当として扱い、stderr に `revise_once: STRATA_TIMESKIP_PROMPT is empty; nothing to ask for` を出して終了コード 2 | `.strip()` 後に空なら同じく終了コード 2 | 前後の空白を除いた文字列を Harness の指示に使う |
| `apps/host/server/timeskip-revise.mjs` | `''` に置換 | 空文字は不足扱いだが、空白だけの文字列は truthy のため検査を通る | 文字列を trim せず JSON の `prompt` として内部 API へ送る。その後、host の `timeskipRevisionMessage()` が前後を trim する |
| `strata_cli/cli.py` の修正コマンド起動 | 継承環境に同名変数があっても、通常の `timeskip run` 経路では CLI の `--prompt` 値で上書き | CLI parser は `--prompt` の引数自体を必須にするが、値が空文字かどうかはここでは検査しない | CLI が各試行の子プロセス環境に設定 |

アプリの `/api/timeskip/start` 経路は空 prompt を拒否し、CLI bridge も空 prompt を拒否します。直接 CLI を使う場合、空の `--prompt` が parser に拒否されるとは限りません。`timeskip-revise.mjs` は `STRATA_HOST_URL` または `STRATA_INTERNAL_SECRET` がない場合も同じ「アプリが実行中である必要がある」というエラーで終了コード 2 になります。環境変数の内容は大文字小文字を変換せず利用します。

## 有効になる条件

- `strata timeskip run` が実行され、少なくとも一度修正コマンドが呼ばれる必要があります。`--revise-command` が省略された CLI 経路では修正コマンドを呼ばず、この変数も子プロセスへ渡しません。
- アプリのホスト経路は `STRATA_TIMESKIP_REVISE` で修正コマンドを上書きできます。未設定なら Node で `timeskip-revise.mjs` を起動し、同スクリプトがこの変数を読みます。上書きコマンドがこの変数を使うかどうかはそのコマンド次第です。
- Python Harness スクリプトでは、この値が空だと Harness の起動や revision を行わず終了します。空でない場合は candidate directory 内の Harness セッションに指示文を追加します。
- 指示文が修正結果を改善したかどうかはこの環境変数や修正コマンドの終了コードでは決まりません。Time-skip 側のチェックと判定処理が結果を決めます。

## 実行時の詳細

CLI は `revise(candidate, prompt, attempt)` を試行ごとに呼び、`{**os.environ, "STRATA_TIMESKIP_PROMPT": prompt, ...}` を作って、candidate directory を作業ディレクトリとして修正コマンドを実行します。したがって同じ run の各試行には、CLI に渡した同じ prompt が再設定されます。起動後に親プロセスの環境を書き換える仕組みはなく、各子プロセス起動時に値が固定されます。

アプリ既定の Node スクリプトは prompt を `/api/internal/timeskip-revise` へ JSON 送信し、host 側は `timeskipRevisionMessage()` で前後の空白を trim して共通指示文に挿入します。応答 stream の `result` は Node スクリプトが stdout に出します。Harness スクリプトは trim 後の prompt を `INSTRUCTIONS` と連結して Harness の session prompt に設定します。

CLI が渡した修正コマンドが非ゼロ終了すると、CLI は stderr/stdout の末尾最大 300 文字を含む `the revision command failed (exit ...)` として Time-skip エラーにします。Python Harness スクリプトは空指示でコード 2、アプリ既定 Node スクリプトはホスト接続失敗などでコード 1 を返します。これらは prompt の長さや妥当性を保証するものではありません。

## 根拠

- `strata_cli/cli.py:353-363` — `--prompt` 必須指定と `--revise-command` の説明。
- `strata_cli/cli.py:1557-1570` — 試行ごとに prompt を子プロセス環境へ設定し、candidate directory でコマンド実行、非ゼロ終了をエラー化。
- `apps/host/server/index.mjs:738-747,1118-1135` — アプリの既定修正スクリプトと `STRATA_TIMESKIP_REVISE` によるコマンド選択、Time-skip 起動への prompt/修正コマンド引き渡し。
- `apps/host/server/index.mjs:1101-1108` — アプリ経由で prompt を trim し、4,000 文字に制限する処理。
- `apps/host/server/timeskip.mjs:430-436,446-455` — prompt 必須の検査、CLI 引数化、detached run 起動。
- `apps/host/server/timeskip-revise.mjs:14-29,52-57` — 環境変数読み取り、空値検査、内部 API への prompt 送信、終了時のエラー処理。
- `apps/host/server/timeskip.mjs:132-145` — host が Node bridge から受け取った prompt の trim と共通指示文への挿入。
- `integrations/harness/revise_once.py:84-100,129-137` — trim と空値エラー、Harness session への指示文の追加。
- `docs/work/IMPLEMENTATION_STATUS.md:361-378` — Harness revision integration の設計・契約の補助資料。挙動の根拠は上記ソース。

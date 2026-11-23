# `STRATA_HY4_SOURCE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash のモデルファイル、Vision ファイル、および付属 tokenizer ファイルを取得するときに使う、HTTP(S) ベース URL の候補を追加します。値から `http` source が作られ、対象ファイル名を末尾に付けた URL が生成されます。Hy4-Flash をメニューに表示する判定にも source の有無が使われます。環境変数を読んでいるのは Strata Terminal の Python 実装で、エンジンの推論時設定ではありません。(`terminal/strata_control/hy4_family.py:87-106,124-134,171-176`、`terminal/setup.py:9965-9973,10049-10064,10143-10170`)

## 値と判定

`sources()` は既定で `os.environ` を参照し、値が truthy のときだけ `_normalise()` に渡します。Python の環境変数値は文字列なので、未設定と空文字列は候補に追加されません。`_normalise()` は文字列全体が小文字の `http://` または `https://` で始まる場合だけ受け付け、末尾の `/` をすべて除去します。前後空白の除去、URL 検証、大小文字の正規化、ポートやパスの検査はありません。したがって `HTTPS://host`、` https://host`、`ftp://host`、`0`、`true` は候補にならず、`https://host/path///` は `https://host/path` に正規化されます。(`terminal/strata_control/hy4_family.py:91-121`)

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Strata Terminal の Hy4 source 選択 | unset と `""` は環境変数由来の候補なし | `https://host/models`、`http://host/dir/` | `HTTPS://host`、` https://host`、`ftp://host`、`0`、`true` |

環境変数由来の source は `kind: "http"` として追加されます。通常のファイルでは `<正規化した base>/<ファイル名>` が URL になり、モデルファイル取得時はこの候補を含む source 一覧を順に試します。(`terminal/strata_control/hy4_family.py:99-111,124-134`)

## 有効になる条件

- Hy4-Flash のモデルファイル取得では、対象ファイルが既に利用可能ならダウンロードせず、`--gguf-dir` で指定した独自フォルダーに対象ファイルがない場合も失敗して source を使いません。通常の取得経路でファイルが不足している場合に `sources()` が呼ばれます。(`terminal/setup.py:10027-10059`)
- Hy4-Flash の Vision ファイル取得では、ローカル候補に対象ファイルが見つからず、取得可能なフォルダーが決まった場合に source 候補を組み立てます。呼び出し元が `endpoint` を渡す場合はその endpoint の URL だけを使い、source 一覧を使いません。(`terminal/strata_control/pictures.py:351-383`)
- `sources()` はビルド macro、GPU backend、OS による値判定を持ちません。Terminal のセットアップと `strata_control.pictures` の Hy4 Vision 取得経路で使われます。設定ファイルの `hy4_source` が渡される Vision 取得では、設定由来 source が環境変数由来 source より前に並びます。モデルファイルのセットアップ取得は `sources()` に設定を渡さず、環境変数由来 source の後に同梱 source を並べます。(`terminal/strata_control/hy4_family.py:91-106`、`terminal/setup.py:10059-10064`、`terminal/strata_control/pictures.py:381`)
- `STRATA_NO_ACQUIRE` が `1`、`true`、`yes`、`on`（前後空白を除去し小文字化した比較）なら取得操作が拒否されます。これは source URL の判定を変えず、取得を止める別の条件です。(`terminal/strata_control/acquisition.py:26,53-54,70-73`)
- Hy4-Flash のメニュー表示は設定済み source がある場合のほか、`STRATA_HY4_SHOW=1` またはサイズが一致するローカルファイルがある場合にも有効です。`STRATA_HY4_SHOW` 単独ではダウンロード source を追加しません。(`terminal/setup.py:9965-9973`、`terminal/tools/strata_mcp.py:646-655`)

## 実行時の詳細

`sources()` は関数呼び出しごとに `os.environ` を参照し、結果を関数内やモジュール内に cache しません。プロセス内で環境辞書が変わった場合、次の呼び出しではその値が使われます。source の並びは、渡された設定の `hy4_source`、環境変数、`terminal/data/hy4-sources.json` の順です。ここでいう優先順位は試行順であり、前の source が失敗した場合は次へ進みます。同梱 JSON の説明文は環境変数で「Overridden」としていますが、実装は同梱 source を除去せず後続候補として追加します。既定 JSON には Hugging Face の source があるため、通常は環境変数未設定でも source 一覧は空になりません。同梱 source ファイルが読めない、または JSON として無効な場合は例外を外へ出さず、その source を省きます。(`terminal/strata_control/hy4_family.py:91-106`、`terminal/data/hy4-sources.json:1-7`)

モデルファイル取得では source ごとに URL を作り、ダウンロードと検証が成功した最初の候補で終了します。失敗による `SystemExit` は捕捉され、後続候補があれば `  [!]  {name}: that source did not work; trying the next one` を出して続行し、最後の失敗は再送出します。source が一つもない場合は `no download source for {name} is configured` と案内を表示してセットアップを終了します。source 一覧があってもどの source も対象ファイルの URL を返さない場合は `no source lists {name}` で失敗します。(`terminal/setup.py:10049-10088,1044-1056`)

Hy4 Vision の取得では設定由来・環境変数由来・同梱 source の URL を並べ、応答しない URL は飛ばします。応答する URL がなければ offline エラー、転送がすべて失敗すれば failed エラーになります。(`terminal/strata_control/pictures.py:377-408`)

## ログと測定値

この環境変数固有の「有効」ログはありません。モデルファイル取得時は、source が空なら `no download source for {name} is configured`、source の試行に失敗して次があるなら `  [!]  {name}: that source did not work; trying the next one` が表示されます。最後の失敗では `download()` の具体的な失敗表示が出てセットアップが終了します。Vision ファイル取得の失敗は `pictures` の `offline` または `failed` 結果になります。(`terminal/setup.py:10059-10088,1044-1056,3471-3539`、`terminal/strata_control/pictures.py:381-408`)

`docs/DETAILS.md` に `STRATA_HY4_SOURCE` の説明は見当たらず、この変数の値や動作を裏付ける測定値も記載されていません。

## 根拠

- 読み取り・正規化・URL 作成: `terminal/strata_control/hy4_family.py:87-134`
- 同梱 source の読込と既定 URL: `terminal/strata_control/hy4_family.py:101-105`、`terminal/data/hy4-sources.json:1-7`
- Terminal メニュー表示と不足モデルファイル取得: `terminal/setup.py:9965-9973,10049-10088`
- tokenizer の source 経路: `terminal/setup.py:10143-10170`、`terminal/strata_control/hy4_family.py:171-176`
- Hy4 Vision の config / env source 取得経路: `terminal/strata_control/pictures.py:419-423,433-457,376-408`
- 取得禁止条件: `terminal/strata_control/acquisition.py:26,53-54,70-73`
- モデル一覧の追加条件: `terminal/tools/strata_mcp.py:646-655`

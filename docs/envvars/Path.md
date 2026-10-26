# `Path`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Windows 上で Cloudflare quick tunnel 用の `cloudflared.exe` を探すとき、検索対象ディレクトリーを列挙するために参照されます。`Path` 自体を Strata の設定値として parse するのではなく、各要素を実行ファイル候補の場所として使います。Linux/macOS では `Path` は参照せず、`PATH` を使います。

## 値と判定

| 条件 | 使用する値 |
|---|---|
| Windows で `Path` が `null` / `undefined` ではない | `Path`。空文字列でも `PATH` には fallback しない |
| Windows で `Path` がない | `PATH`。これもなければ空文字列 |
| Windows 以外 | `PATH`。なければ空文字列 |

選ばれた文字列を Windows ではセミコロン（`;`）、それ以外ではコロン（`:`）で分割します。各要素の前後空白を削り、要素全体を囲む `"` を除いてから `cloudflared.exe`（Windows）または `cloudflared`（それ以外）を連結します。空要素は候補追加時に無視されます。文字列全体の trim、環境変数値の妥当性検証、または `Path` と `PATH` の値の結合は行いません。Windows の重複候補判定では生成したパスを小文字化します。

## 有効になる条件

通常の検索が有効で、`STRATA_CLOUDFLARED` が truthy でない場合に候補探索へ進みます。`STRATA_CLOUDFLARED_SEARCH=own` の場合は通常検索を止めるため、`Path` / `PATH` は使われません。ただし Strata 自身の connector folder と optional component folder は引き続き候補になります。`STRATA_CLOUDFLARED` に truthy な値があれば、その値だけが connector 候補となり、`Path` / `PATH` を含む探索は行われません。

候補に追加されたファイルも、そのまま採用されるわけではありません。通常ファイルであることと実行可能性を確認し、`--version` の実行結果を調べます。Strata は `2022.1.0` より古いと判定した版を除外します。バージョンを読み取れない出力は、ソース上では拒否理由にしません。

## 実行時の詳細

ホストサーバー起動時に connector installer が作られ、初回 `cloudflare.inspect()` が呼ばれます。installer の `look()` は `findConnector()` を呼び、その候補列挙で `env.Path` / `env.PATH` を参照します。installer の既定 `env` は `process.env` です。`look()` ごとに候補を作り直し、この変数専用の static cache はありません。後続の inspect / locate でも同じ探索関数を通ります。

見つかった connector のパスと検索元は connector 情報として保持され、`describeConnector()` は「バージョン・パス・見つかった場所」を表示用文字列にします。適切な候補がなく、発見したが起動できない・cloudflared ではない・古すぎる候補があった場合は、その状況に応じたメッセージを返します。`Path` の値そのものをログへ出す処理は、このコードにはありません。

## 根拠

- Windows 判定、`Path` 優先と `PATH` fallback、区切り文字、要素整形、候補重複排除: `apps/host/server/cloudflared-find.mjs:42-70`。
- 候補のファイル確認、`--version` 実行、バージョン条件、採用・skip: `apps/host/server/cloudflared-find.mjs:20-31,73-110`。
- installer の env 既定値と毎回の探索呼び出し: `apps/host/server/cloudflared-install.mjs:34-45`。
- ホスト起動時の installer 作成と初回 inspect: `apps/host/server/index.mjs:932-934`。
- 関連資料の `cloudflared` の説明は Cloudflare tunnel をインターネット公開の例として挙げるにとどまり、`Path` の優先規則は記載していません: `docs/DETAILS.md:548`, `docs/TERMINAL_LAUNCH.md:62`。

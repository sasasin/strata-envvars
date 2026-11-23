# `PERL5LIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身の Perl 機能を設定する読み取り箇所は見つからなかった。Strata のホスト側コードは `PERL5LIB` を `PATH_LISTS` に登録し、AppImage 起動元の環境を外部プログラム用に復元・清掃するとき、他のパスリスト変数と同じ扱いで値をコピーまたは AppImage 内の項目を除去する（`app/host/server/external-env.mjs:25-26,43-57,63-71`）。

この環境は、ファイル選択ダイアログ、ブラウザーやファイルを開くプログラム、通知、エージェント用環境の組み立てなどで使われる（`app/host/server/chat-files.mjs:89-94`、`app/host/server/folder-dialog.mjs:112-126,153-164`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/open-text-file.mjs:26-36`、`app/host/server/artifacts.mjs:5-6`、`app/host/server/agent/harness-runtime.mjs:25-36`）。`PERL5LIB` 自体がそれらの処理を有効化するわけではない。

## 値と判定

`PERL5LIB` 固有の値 parse、既定値、CLI 引数との優先順位はない。`PATH_LISTS` に名前があるため `withoutAppImage` が環境オブジェクトの `PERL5LIB` プロパティを参照し、AppImage の場所を含む項目を除く。文字列比較や trim、大小文字変換、数値変換はしない（`app/host/server/external-env.mjs:25-26,43-57`）。

したがって `0`、`1`、`true`、`false`、`0anything` は真偽値や数値として判定されず、通常は文字列としてそのまま保持される。記録なしの AppImage 清掃時だけ、コロン区切りの要素に `APPDIR` 内の文字列が含まれるかで残る部分が変わる。Strata が `PERL5LIB` の値自体を無効と判定する値はない。

| 条件 | 未設定 | 設定値の扱い |
|---|---|---|
| AppImage 外、かつ `STRATA_ORIGINAL_ENV` なし | 未設定のまま | 空文字を含め、値をそのまま複製する（`app/host/server/external-env.mjs:67-68`） |
| `STRATA_ORIGINAL_ENV` に復元可能な起動元環境がある | 起動元にもなければ未設定 | 記録された起動元の `PERL5LIB` をそのまま使う。現在の AppImage 環境側の値で上書きしない（`app/host/server/external-env.mjs:28-40,67-71`） |
| AppImage 内で起動元記録がない | `APPDIR` があり、値がなければ未設定 | `APPDIR` がある場合、コロンで分割して空要素と AppImage ディレクトリ内の要素を除去し、残りを再結合する。残りがなければ変数自体を削除する（`app/host/server/external-env.mjs:43-57`） |

AppImage 内の要素とは、`APPDIR` と完全一致するか、`APPDIR/` または `APPDIR//` で始まる文字列を指す。比較はコードどおりの文字列比較で、パス正規化はしない。たとえば `APPDIR=/opt/strata` のとき、`/opt/strata/lib` と空要素は除外されるが、`/opt/strata-old/lib` や ` /opt/strata/lib` はこの判定では除外されない。空文字だけの値は分割後に要素が残らないため削除される。`APPDIR` が空なら path-list の清掃自体を行わない（`app/host/server/external-env.mjs:45-55`）。

## 有効になる条件

- `externalEnvironment` の環境変換は、`APPIMAGE` または `APPDIR` が真値、あるいは `STRATA_ORIGINAL_ENV` が設定されている場合に行われる。それ以外は入力環境を複製するだけ（`app/host/server/external-env.mjs:60-71`）。
- 起動元記録が base64 として空でなく、NUL 区切りの `NAME=value` 項目から1個以上のキーを復元できた場合、その記録を使う。復元できない場合は `withoutAppImage` の清掃経路になる（`app/host/server/external-env.mjs:28-40,67-71`）。
- 記録なしの清掃で `PERL5LIB` の要素除去が起きるには `APPDIR` が必要で、値が文字列である必要がある（`app/host/server/external-env.mjs:45-55`）。
- エージェント用 `agentEnvironment` は `externalEnvironment` の結果から `KEEP` 正規表現に合う名前だけを残す。`PERL5LIB` はその正規表現に含まれないため、`extra` で明示的に渡さない限り、Harness の子プロセス環境からは除かれる（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。
- `externalEnvironment` の呼び出し側が `extra` を渡す場合は、変換後にその値が最後にマージされるため、`extra.PERL5LIB` が結果を上書きできる（`app/host/server/external-env.mjs:63-71`）。

## 実行時の詳細

`externalEnvironment` は呼び出し時に渡された環境（既定は `process.env`）を読み、毎回新しいオブジェクトを返す。モジュール読み込み時の値キャッシュはない。記録環境が使われる場合は `STRATA_ORIGINAL_ENV` を base64 decode し、NUL 区切りから環境オブジェクトを復元する。記録が使えない場合、`withoutAppImage` は入力を複製し、AppImage 固有変数を削除したうえで `PATH_LISTS` の各値から `APPDIR` 内の要素を除く（`app/host/server/external-env.mjs:15-26,28-57,63-71`）。

この helper 自体は子プロセスを起動せず、ログも出さない。呼び出し側が返却値を `spawn` / `execFile` の `env` として渡す。エージェント経路ではさらに allowlist で環境を絞る（`app/host/server/chat-files.mjs:89-94`、`app/host/server/folder-dialog.mjs:117-126,153-164`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## 根拠

- `app/host/server/external-env.mjs:25-26` — `PERL5LIB` を path-list 名の配列に登録。
- `app/host/server/external-env.mjs:28-40` — 起動元環境の記録復元。
- `app/host/server/external-env.mjs:43-57` — AppImage 固有環境の削除と path-list の要素除去。
- `app/host/server/external-env.mjs:60-71` — AppImage 判定、入力環境と `extra` の優先関係。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — エージェント環境の allowlist と子プロセスへの引き渡し。
- `app/host/server/chat-files.mjs:89-94`、`app/host/server/folder-dialog.mjs:117-126,153-164`、`app/host/server/app-ui.mjs:39-59`、`app/host/server/open-text-file.mjs:26-36`、`app/host/server/artifacts.mjs:5-6` — 他の外部プログラム起動時の helper 利用。

# `XDG_CONFIG_DIRS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。候補名の直接参照と env helper 経由の参照を Strata 所有ソース全体で検索した。

## 役割

Strata は `XDG_CONFIG_DIRS` を通常の設定値として読み取っていない。Linux AppImage から外部プログラムへ渡す環境を作るとき、path-list 名簿に含め、AppImage のディレクトリを含む値を清掃する。AppImage 起動時に記録した元環境が利用できる場合は、その元の `XDG_CONFIG_DIRS` を復元する。対象は Strata 自身の設定ではなく、外部プログラム向け環境の整形である（`apps/host/server/external-env.mjs:1-13,25-26,43-57,63-71`）。

## 値と判定

| 状況 | Strata の処理 |
|---|---|
| AppImage 外で、`STRATA_ORIGINAL_ENV` もない | 環境オブジェクトをコピーして返す。`XDG_CONFIG_DIRS` は未設定・空文字を含めそのまま（`apps/host/server/external-env.mjs:60-70`）。 |
| AppImage の launcher が記録した元環境が有効 | `STRATA_ORIGINAL_ENV` を Base64 として UTF-8 に戻し、NUL 区切りの `NAME=value` 項目をオブジェクト化して返す。従って記録に `XDG_CONFIG_DIRS` があればその値が渡り、記録になければ設定されない。これは現在の AppImage 側の値を編集する経路ではない（`apps/host/server/external-env.mjs:28-40,67-71`; launcher の記録は `apps/desktop/scripts/repack-appimage.sh:52-58`）。 |
| AppImage 内で元環境記録がない、または記録を復号して有効な項目を得られない | `APPDIR` が空でなければ値を `:` で分割し、空要素と AppImage 内のパス要素を取り除く。残った要素は `:` で結合し、1 個も残らなければ変数自体を削除する。`APPDIR` が空なら path-list 清掃はしない（`apps/host/server/external-env.mjs:43-57,67-70`）。 |

清掃時の「AppImage 内」は、要素が `APPDIR` と完全一致するか、`APPDIR/` または `APPDIR//` で始まる場合である。値全体の trim、パス正規化、重複排除、標準既定値の追加は行わない。空文字は `''.split(':')` によって空要素となり、`APPDIR` がある清掃経路では削除されて未設定になる。負値や数値変換は関係しない。配列要素を `out[name]` で動的に参照・更新しており、`XDG_CONFIG_DIRS` は `PATH_LISTS` の一項目としてこの処理を受ける（`apps/host/server/external-env.mjs:25-26,49-55`）。

## 有効になる条件

- 外部プロセス用環境を整える呼び出しで適用される。AppImage 起動状態は OS 判定ではなく `APPIMAGE` または `APPDIR` の有無で識別する。元環境記録 `STRATA_ORIGINAL_ENV` がある場合も、記録の復元経路へ入る（`apps/host/server/external-env.mjs:60-70`）。
- 古い AppImage など記録を使えない場合の清掃は、`APPDIR` が truthy のときだけ実行される。`APPDIR` が空で記録も使えない場合、helper は値をそのままコピーする（`apps/host/server/external-env.mjs:43-57,67-70`）。
- `externalEnvironment` の `extra` 引数は最後に合成されるため、呼び出し元が明示的に `extra.XDG_CONFIG_DIRS` を渡す場合は復元・清掃後の値を上書きする（`apps/host/server/external-env.mjs:63-71`）。確認した標準呼び出しの多くは追加値を渡さない。
- Agent Harness 用環境では `externalEnvironment(base)` の結果から `XDG_.*` 名を許可し、secret 名に該当しない限り子プロセス環境にコピーする。Strata は Harness を起動するときにその環境を渡す（`apps/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## 実行時の詳細

helper は呼び出し時に渡された `env`（既定は `process.env`）を読み、戻り値の新しいオブジェクトを作る。`XDG_CONFIG_DIRS` や `externalEnvironment` の結果を static 変数などへ cache する実装はないため、各呼び出しはその時点の環境を使う（`apps/host/server/external-env.mjs:28-57,67-71`）。launcher 側では AppImage の hook が環境を変更する前に元環境を `env -0 | base64` で `STRATA_ORIGINAL_ENV` に記録する（`apps/desktop/scripts/repack-appimage.sh:52-58`）。

この環境 helper は Linux の folder chooser（zenity、kdialog、gdbus）、ファイル・artifact opener（xdg-open など）、通知、ブラウザー opener、Harness 起動などの子プロセス起動へ接続されている（`apps/host/server/folder-dialog.mjs:105-119,142-157`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/artifacts.mjs:5-6,27-30`; `apps/host/server/app-ui.mjs:34-58`; `apps/host/server/agent/harness-runtime.mjs:26-36,75-83`）。そのため `XDG_CONFIG_DIRS` に関する観測可能な効果は、これらの子プロセスへ渡す環境値が復元・清掃・上書きされること。helper 自体はログ、警告、終了、エラーを出さない（`apps/host/server/external-env.mjs:43-71`）。各外部プログラムや desktop 側でこの値がどう使われるかは Strata の挙動として扱わない。

## 根拠

- `apps/host/server/external-env.mjs:25-26,49-55` — 動的な path-list 処理と `XDG_CONFIG_DIRS` の登録。
- `apps/host/server/external-env.mjs:28-40,43-57,60-71` — 元環境の復号、AppImage path 清掃、分岐と `extra` の優先順位。
- `apps/desktop/scripts/repack-appimage.sh:52-58` — launcher による元環境の記録。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — `XDG_.*` 変数の agent 環境への転送と Harness 起動。
- `apps/host/server/folder-dialog.mjs:105-119,142-157`; `apps/host/server/chat-files.mjs:89-94`; `apps/host/server/artifacts.mjs:5-6,27-30`; `apps/host/server/app-ui.mjs:34-58` — helper を経由する外部プロセス起動箇所。

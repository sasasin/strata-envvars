# `STRATA_ENGINE_BUNDLE_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main` で未変更。外部ライブラリの環境変数は対象外。

## 役割

アプリに同梱された Strata engine パッケージを探すディレクトリを指定します。Control が利用可能なホストの起動時に、その中の適合する engine を通常の components engine store にコピーする処理と、導入後に同梱コピーを削除できるか確認する処理の両方で使われます。engine のコピーはネットワークからの取得ではありません（`apps/host/server/bundled-engine.mjs:2-10,164-170`）。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `resolve(HERE, '..', '..', 'engine-bundle')` を使用。インストール構成では `<install>/engine-bundle`。 |
| 空文字 | JavaScript の `||` により未設定と同じ既定ディレクトリを使用。 |
| 非空文字列 | 文字列を加工せず bundle のパスとして使用。相対パスは Node.js のプロセス作業ディレクトリ基準。空白の trim、存在確認、文字列形式の検査はこの変数に対して行わない。 |
| 指定先が存在しない、または読み取れる manifest 付き package がない | installer は `{ action: 'none' }` を返す。 |

変数専用の CLI 引数や別の環境変数との値競合・上書き処理はありません。値は server module の初期化時に2回読み取られ、install と cleanup に同じ選択規則で渡されます。起動後に `process.env` を変更しても、既に選択されたパスは再評価されません（`apps/host/server/index.mjs:145-151`）。

## 有効になる条件

- `findControl()` が有効な Control を返し、かつ `STRATA_NO_BUNDLED_ENGINE` が truthy でないときだけ自動導入を開始します。Control がないソース checkout などではこの変数を指定しても自動導入されません。`STRATA_NO_BUNDLED_ENGINE` は設定値を parse せず JavaScript の truthiness で判定されるため、空文字以外の文字列で導入を止めます（`apps/host/server/index.mjs:73,123,145-148`; `apps/host/server/control-runtime.mjs:59-74`）。
- `STRATA_ENGINE_BUNDLE_DIR` はコピー元だけを変えます。コピー先は `componentsDirectory()/engine` であり、`STRATA_COMPONENTS_DIR` などの components 設定によって決まります（`apps/host/server/index.mjs:147`; `apps/host/server/bundled-engine.mjs:208-209`; `apps/host/server/control-runtime.mjs:26-31`）。
- bundle 内の manifest が読めて package として有効であることが必要です。OS platform が指定された場合は一致する package に絞られますが、ホストからの呼び出しは platform を指定しません。GPU backend が判定できる場合は合う backend を選び、適合する GPU package が一つもない場合は `wrong-make` になります。CUDA package の最低 NVIDIA driver 条件も選択に使われます。backend 判定には `STRATA_ENGINE_BACKEND` が影響します（`apps/host/server/bundled-engine.mjs:27-34,168-205`; `apps/host/server/index.mjs:147`）。
- 同じ variant の同等以上の engine が store にあり、同一 package が破損していなければ既存 package を保持します。bundle 削除は導入結果が `installed` / `kept` / `repaired` の場合だけ試行され、store 側に bundle 内の全 package が同一内容で存在すると検証できた場合に限ります。macOS app bundle 内は署名後の内容を保つため削除されません（`apps/host/server/bundled-engine.mjs:216-231,276-319`）。

## 実行時の詳細

ホスト module の初期化時に bundle path を決め、条件を満たすと `installBundledEngine()` を非同期で開始します。installer は bundle の直下にある隠しディレクトリ以外を走査し、manifest を読みます。ファイルのサイズと SHA-256 を照合してから、components の一時ディレクトリへコピーし、再検証後に最終位置へ rename します。新しい package が既存の同一 variant より古ければ導入せず、同じ package の破損を検出した場合は修復します（`apps/host/server/bundled-engine.mjs:168-178,206-263`）。

導入中は `/api/control/status` の `engineSetup` が true になり、engine が利用不可なら「The engine that came with the app is being set up. This takes a minute the first time.」という notice が返ります。promise の成功・失敗どちらでも settled になり、その後 `engineSetup` は false です（`apps/host/server/index.mjs:152-153,1291-1302`）。

コピー成功、manifest 不一致、コピー時の拒否などはホストの `console.log` に `bundled engine ...` の行を出します。backend が異なる場合は `wrongMakeNotice()` の文面を出力します。例外を外側で捕捉した拒否結果は、この経路では理由をログ出力しません。bundle cleanup の保持・削除結果も条件に応じてログ出力されます（`apps/host/server/bundled-engine.mjs:186-188,234-267,302-319`; `apps/host/server/index.mjs:147,156`）。

## 根拠

- 環境変数の2つの読み取り、fallback、導入条件、cleanup への受け渡し: `apps/host/server/index.mjs:145-153`。
- Control の検出条件: `apps/host/server/control-runtime.mjs:52-74`。
- bundle の存在確認、manifest 読み取り、OS/backend/driver による選択、既存 engine の扱い、検証付きコピー: `apps/host/server/bundled-engine.mjs:27-34,168-263`。
- bundle cleanup の条件とログ: `apps/host/server/bundled-engine.mjs:276-319`。
- UI で観測できる setup 状態: `apps/host/server/index.mjs:1291-1302`。

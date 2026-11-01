# `GDK_PIXBUF_MODULE_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の起動元環境を保存する AppImage 経路と、外部プログラム用環境の処理を対象とする。外部ライブラリ側の動作は対象外。

## 役割

Strata の engine や GPU backend がこの値を設定として解釈する箇所は確認できません。Node 側の `externalEnvironment()` が、この名前を AppImage 専用変数の一覧に含めています。AppImage から外部プログラムを起動するとき、Strata が渡す環境からこの変数を除くか、AppImage 起動前に記録した環境の値を使います。対象となる呼び出しにはフォルダー選択（`zenity`、`kdialog`、`gdbus`）、`xdg-open`、ファイルを開く処理があります。coding assistant の shell 環境を組み立てるときにも helper を通りますが、その環境は `KEEP` の whitelist にないため、このキーは通常除かれます。

## 値と判定

値の内容を数値・真偽値・パスとして parse したり、空文字を個別に判定したりするコードはありません。Node の環境オブジェクトをコピーし、キー名で削除・復元します。

| 呼び出し元の環境 | 外部プログラムへ渡す値 |
|---|---|
| `APPIMAGE` と `APPDIR` がどちらも falsy で、`STRATA_ORIGINAL_ENV` も falsy（未設定または空文字） | 呼び出し時点の `GDK_PIXBUF_MODULE_FILE` をそのまま引き継ぐ。未設定なら未設定のまま。 |
| AppImage 環境（`APPIMAGE` または `APPDIR` が truthy）で、`STRATA_ORIGINAL_ENV` から有効な元環境を復元できる | 復元した元環境にこのキーがあればその値、なければ未設定。現在の AppImage 側の値は使わない。 |
| AppImage 環境で元環境の記録がない、空、または復元できない | `withoutAppImage()` がこのキーを削除するため、外部プログラムでは未設定。 |
| AppImage 外でも `STRATA_ORIGINAL_ENV` がある | AppImage 環境と同じく元環境を復元する。復元できなければ `withoutAppImage()` による除去を行う。 |

`STRATA_ORIGINAL_ENV` の復元は、base64 を UTF-8 に戻し、NUL 区切りの `NAME=value` 項目をオブジェクトにする処理です。復元できた元環境オブジェクトが選ばれると、現在の環境をマージせず置き換えます。`externalEnvironment` の `extra` 引数がある場合だけ、そのキーが最後に追加・上書きされます。

## 有効になる条件

- AppImage 外で通常起動した場合、Strata はこの変数を加工しません。
- `APPIMAGE` または `APPDIR` が truthy の場合は、元環境記録の有無に応じて復元または削除します。`APPDIR` がある場合、AppImage のディレクトリーを含む `GTK` / `GDK` / `GIO` などの値を除く共通処理もありますが、このキーは専用一覧で無条件に削除されるため、ディレクトリー文字列の一致には依存しません。
- `apps/desktop/scripts/repack-appimage.sh` は AppImage の `AppRun` に `STRATA_ORIGINAL_ENV` を記録する hook を追加します。この記録に元の `GDK_PIXBUF_MODULE_FILE` が含まれるかどうかで、外部プログラムへ値が戻るかが決まります。
- `agentEnvironment()` は helper の結果から `KEEP` に一致するキーだけを採用します。`GDK_PIXBUF_MODULE_FILE` はその whitelist に一致しないため、通常は agent shell に渡りません。関数の `extra` が明示的に同名を渡せば最後の merge で追加されます。
- この helper の利用は Linux AppImage の外部プログラム起動経路に限られませんが、同 helper のコメント上、加工の目的と条件は AppImage 環境の分離です。CUDA/HIP/SYCL、モデル状態、Strata の CLI オプションによる判定はありません。

## 実行時の詳細

`externalEnvironment(env = process.env, extra = {})` は呼び出し時に `env` を参照し、AppImage 外かつ `STRATA_ORIGINAL_ENV` が falsy ならコピーを返します。AppImage 環境または truthy な記録がある場合、記録された元環境を優先し、記録を使えないときはコピーから `APPIMAGE_ONLY` の各キーを削除します。その一覧に `GDK_PIXBUF_MODULE_FILE` が明示されています。関数結果は `zenity` / `kdialog` / `gdbus` 等の子プロセス、`xdg-open`、ファイル opener に渡されます。agent shell にはさらに `KEEP` whitelist が適用され、通常このキーは除かれます。関数内に cache はなく、呼び出しごとに環境オブジェクトから組み立てられます。

このキーについて Strata 固有のログ、警告、終了・失敗経路はありません。観測できる Strata 側の差は、上記条件で起動された子プロセスの環境にキーが存在するか、どの値が渡るかです。子プロセスや外部ライブラリがその値をどう使うかは、この調査の対象外です。

## 根拠

- `apps/host/server/external-env.mjs:17-24` — `GDK_PIXBUF_MODULE_FILE` を含む `APPIMAGE_ONLY` の一覧。
- `apps/host/server/external-env.mjs:28-40` — `STRATA_ORIGINAL_ENV` の decode と `NAME=value` の復元。
- `apps/host/server/external-env.mjs:43-57` — 環境のコピーと AppImage 専用キーの削除。
- `apps/host/server/external-env.mjs:60-70` — AppImage 判定、通常環境の passthrough、元環境優先と fallback。
- `apps/desktop/scripts/repack-appimage.sh:52-58` — `AppRun` に起動元環境を記録する hook を追加。
- `apps/host/server/folder-dialog.mjs:110-129,146-157` — フォルダー選択・portal 呼び出しへの環境受け渡し。
- `apps/host/server/chat-files.mjs:85-94`, `apps/host/server/artifacts.mjs:5-8` — opener、artifact 起動での helper 利用。
- `apps/host/server/agent/harness-runtime.mjs:20-36` — agent shell が helper 経由で環境を作り、`KEEP` whitelist で絞る処理。
- 候補一覧には `docs/envvars/000_envvers.md:375` に記載があります。コード上では外部子プロセス用環境を処理する helper が当該名を明示的に操作しており、値の内容を Strata の機能設定として読む実装は見つかりませんでした。

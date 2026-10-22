# `STRATA_CLOUDFLARED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有コード。外部プログラム cloudflared 自身が読む設定は扱わない。

## 役割

Cloudflare tunnel の実行ファイル `cloudflared` を探すとき、使用するファイルのパスを明示します。Strata CLI のアクセス設定・quick tunnel と、デスクトップホストの Cloudflare connector 検出の両方で参照されます。変数は cloudflared に渡す設定ではなく、Strata 側の探索先指定です。

## 値と判定

| 実行経路 | 未設定・空値 | 空でない値 |
|---|---|---|
| Python CLI (`strata_cli/launch/access.py`) | PATH と OS ごとの既定場所を探索 | 前後の空白を `strip()` した値だけを候補にする。空白だけなら未設定と同じ |
| デスクトップ host (`apps/host/server/cloudflared-find.mjs`) | Strata 内の connector、component、PATH、OS ごとの既定場所を探索 | 値をそのまま唯一の候補にする。JavaScript の truthy 判定のため空文字 `""` は未設定と同じ。空白だけの値は候補として扱う |

値はパス文字列として扱われ、真偽値・数値として parse されません。明示パスが実行可能でない、起動できない、cloudflared と判定できない、またはバージョンが古い場合、両経路とも他の場所へ探索を戻しません。空白の除去規則は経路間で異なります。

## 有効になる条件

- Python 経路では `cloudflared_info()` を呼ぶアクセス選択・tunnel 起動時に使われます。候補ファイルが通常ファイルであり、Windows 以外では実行権限があり、`cloudflared --version` が成功し、認識できるバージョンが最低 `2022.1.0` 以上（またはバージョン文字列を読めないが cloudflared と確認できるもの）である必要があります。
- デスクトップ経路では `connectorCandidates()` の探索時に使われます。候補は通常ファイルかつ実行可能で、`--version` の出力に cloudflared 名またはバージョンがあり、読み取れたバージョンが最低 `2022.1.0` 以上である必要があります。バージョンが出力から読めない場合も、cloudflared と確認できれば拒否されません。
- この変数は tunnel 機能を有効化しません。アクセス種別や UI 操作で Cloudflare tunnel が選択・開始される場合に、connector の検索に影響します。

## 実行時の詳細

Python の `_cloudflared_places()` は各探索時に環境変数を読みます。明示パスが使えない場合、アクセス選択では「cloudflared is not installed on this computer」、起動時には `missing_helper()` の案内が返ります。見つかった実行ファイルは `start_tunnel()` が `tunnel --no-autoupdate --url http://127.0.0.1:<port>` で起動します。

デスクトップ host は起動時に `createConnectorInstaller()` を作り、その `locate()` / `inspect()` が探索を行います。明示パスが使えない場合、明示候補だけが検査されます。インストール処理 `ensure()` も先に同じ探索を行い、候補が無効と判定された場合は理由を返して終了します。適切な connector が見つからず、無効候補のエラーもない場合に限り、通常の取得条件に従って Strata 管理フォルダーへ connector を取得できます。

どちらの経路も、環境変数を各 lookup の中で参照し、値を static cache していません。Python は `cloudflared --version` の結果をパスとファイル更新時刻の組で cache しますが、候補パス自体は再探索されます。デスクトップ host では connector 検出結果が前回の `inspect` / `locate` の状態として保持され、次の lookup で更新されます。

## 根拠

- Python の値処理と候補順: `strata_cli/launch/access.py:70-95`。
- Python の通常ファイル・実行権限・version 検査と最低版: `strata_cli/launch/access.py:97-137`。
- Python の検出結果表示・起動への適用: `strata_cli/launch/access.py:242-255,270-282,332-355`。
- デスクトップ host の値判定・候補順: `apps/host/server/cloudflared-find.mjs:42-70`。
- デスクトップ host のファイル・version 検査、候補の選択と失敗理由: `apps/host/server/cloudflared-find.mjs:73-125`。
- installer が lookup 結果を使い、既存 connector 不在時に取得へ進む条件: `apps/host/server/cloudflared-install.mjs:34-52`。
- host における installer と tunnel の接続: `apps/host/server/index.mjs:918-919`。

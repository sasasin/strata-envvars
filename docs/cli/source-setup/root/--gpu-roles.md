# `--gpu-roles`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新用 wrapper も同じ parser に委譲） |
| オプション | `--gpu-roles` |
| 別名 | なし |
| 値 | `LIST`。カード番号と `main` / `helper` / `off` の組を指定 |
| 既定値 | `None`（省略時は明示ロールを設定しない） |

## 役割

setup 時に GPU ごとの役割を明示します。`main` は回答の最後の処理を担当し、`helper` は複数 GPU 利用時の補助カード、`off` は利用しないカードです。指定しなかったカードも `off` として扱われます。例は `--gpu-roles 1=main,0=helper` です（`setup.py:8466-8467`）。

## 使い方

```sh
./setup.sh --setup --gpu-roles 1=main,0=helper
```

`setup.sh` は引数をそのまま `setup.py` に渡し、Windows の `START-HERE.bat` も `setup.py %*` として委譲します。`update.sh` / `UPDATE.bat` もオプションを `setup.py` に渡す旨を記載しています（`setup.sh:6-13,76`、`START-HERE.bat:44-54`、`update.sh:5-6`、`UPDATE.bat:2-6`）。

## 値・既定値・validation

parser は `metavar="LIST"` の文字列引数として登録し、`choices` や既定値を指定していません（`setup.py:8466-8467`）。値の解釈は `strata_control/gpu_roles.py` の `parse_roles()` が行います。setup 側は `if a.gpu_roles` の条件で処理するため、空文字列を明示しても値省略と同じくロール解析を行いません（`setup.py:8578-8579`）。

- `番号=役割` または `番号:役割` の形式で指定します。カンマまたはセミコロンで複数項目を区切れます。空白は trim され、役割名は小文字に変換されます（`strata_control/gpu_roles.py:218-230`）。
- カード番号は数字、役割は `main` / `helper` / `off` のいずれかです。同じ番号を重複指定できず、`main` は最大 1 枚です。空の指定、形式不正、未知の役割、複数の `main` は `ValueError` になります（`strata_control/gpu_roles.py:221-238`）。
- setup の CLI 呼び出しでは `parse_roles()` に検出カード一覧を渡していないため、この段階では番号が実在カードか照合しません（`setup.py:8582-8585`）。後続の GPU 選択・適合処理で対象カードが利用できない場合の扱いは、OS、backend、モデルなどの経路にも依存します。
- 少なくとも 1 枚は `main` または `helper` にする必要があります。全カード `off` は setup では parser error になります（`setup.py:8587-8589`）。

`setup.py` は明示された `main` がない場合、オンになっているカード番号のうち最大の番号を Main にします。Helper はそれ以外のオンカードです。複数カードは Helper の昇順の後に Main を並べ、`a.gpus` に渡します。1 枚なら `a.gpu` に渡します（`setup.py:8590-8598`）。ここでの Main の選出はカード番号基準であり、別の UI 推薦ロジックの規則をこの CLI 経路に当てはめていません。

## 効果・相互作用

`--gpu` または `--gpus` と同時に使うことはできません。両方が指定されると `ap.error()` で停止します（`setup.py:8579-8586`）。`--gpu` のカンマ区切り値は先に `--gpus` 相当に変換されるため、そのケースもこの排他判定に入ります（`setup.py:8571-8577`）。

GPU 選択・適合処理後、選択済み GPU を元に `gpu_roles` を設定へ保存します。最終的に複数 GPU の場合は `gpu_order: as_given` も記録し、`gpus_asked` を true にします。保存対象には入力時の役割と、その後の選択処理で残ったカードの集合が反映されます（`setup.py:9637-9654`）。役割設定はモデルの setup 設定に記録されるため、その後の実行でも利用される設定です（`setup.py:8466-8467,9647-9654`）。

明示ロールは `_roles_explicit` と `_roles` に保持され、単一 GPU への縮退や GPU 選択後に保存される値にも使われます（`setup.py:8592-8598,8796-8798,9643-9654`）。したがって、入力に複数のオンカードがあっても後続のモデル適合判定で選択カード数が変わる場合、設定へ保存される `gpu_roles` が元の指定と完全一致するとは限りません（`setup.py:9647-9654`）。

## 適用条件・副作用・失敗経路

このオプションは `setup.py` の共通 parser に属し、wrapper ごとの別解釈はありません。`setup.py` はプラットフォームや backend に応じて専用経路へ分岐するため、役割指定後の GPU 検出・選択・setup 成功可否は環境依存です（`setup.py:8561-8564,8578-8598`）。指定が有効なら GPU の選択状態とモデル設定に影響します。setup 全体が行うダウンロード、設定保存、engine の準備などの処理は本オプションだけに固有の副作用としては特定できません。

不正な値は `parse_roles()` の `ValueError` を `--gpu-roles: ...` として `ap.error()` に渡します。全カード Off、または `--gpu` / `--gpus` との併用も `ap.error()` による失敗です（`setup.py:8579-8589`）。`argparse` の parser error は usage とエラーを出して終了します。カード番号の実在性・利用可能性に関する後続エラーは setup の GPU/backend 経路に委ねられます。

## 根拠

- parser 定義と説明: `setup.py:8466-8467`
- GPU オプションの排他、値の解析、Main/Helper 化と選択順: `setup.py:8571-8598`
- ロール文法と validation: `strata_control/gpu_roles.py:218-244`
- 選択後の設定保存: `setup.py:9637-9654`
- wrapper の引数委譲: `setup.sh:6-13,76`、`START-HERE.bat:44-54`、`update.sh:5-6`、`UPDATE.bat:2-6`

この調査では指定 revision のソースと文書索引を確認しました。同一 revision の CLI `--help` は実行しておらず、Release 配布物との照合もしていません。

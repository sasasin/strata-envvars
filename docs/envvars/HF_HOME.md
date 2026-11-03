# `HF_HOME`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の DFlash2 drafter を用意するとき、すでに Hugging Face Hub 形式で保存されている pinned snapshot を探す場所の一つを指定します。見つかったファイルはサイズと SHA-256 を検査し、合格すればそこから読み込みます。`HF_HOME` 自体は DFlash2 の選択や推論動作を切り替えません。

## 値と判定

Strata は `os.environ.get("HF_HOME")` の真偽値だけを判定し、真なら `Path(os.environ["HF_HOME"]) / "hub"` を検索 root に追加します（`strata_control/drafting_fetch.py:76-85`）。

| 状態 | Strata の処理 |
|---|---|
| 未設定 | `HF_HOME` の root を追加しない |
| 空文字 | `os.environ.get()` が偽になるため root を追加しない |
| 非空文字 | 文字列をそのまま `Path` に渡し、末尾に `hub` を結合する |

文字列の parse、trim、存在確認、展開（`~` など）、絶対パス化はこの箇所ではしません。相対パスはプロセスの作業ディレクトリからの相対パスです。パスが有効かどうかは、その下の snapshot ファイルを調べる段階で決まります。

## 有効になる条件

`HF_HOME` は `strata_control.drafting_fetch.ensure()` が実際に Hub snapshot 候補を探すときだけ参照されます。取得済み pack がすでに ready なら早期 return するため読みません。また `files` を指定する内部テスト用経路でも snapshot 探索を省きます（`strata_control/drafting_fetch.py:144-160`）。

主な呼び出し経路は次のとおりです。

- `strata drafting fetch` は `ensure()` を呼びます。`--if-needed` を指定した場合は、モデルの選択が DFlash2 を必要とし pack が未取得のときだけ呼びます（`strata_cli/drafting_cmd.py:81-87,103-123`）。
- Terminal の Load は、選択したモデル・backend などから DFlash2 が必要で、pack が未取得と判定されたときに `ensure()` を呼びます。取得できない場合も launch を止めず、MTP があれば MTP、それ以外は drafter なしで開始する旨を警告します（`strata_cli/launch/runner.py:1581-1606`）。
- `strata drafting plan` は計画を表示しますが、`ensure()` を呼ばないため `HF_HOME` の snapshot を探索しません（`strata_cli/drafting_cmd.py:88-102`）。

選択が `off` / MTP である場合、またはモデル・engine・カード条件により DFlash2 を使わない場合、Load は pack の取得を要求しません。選択判定は `strata_control/drafting.py:648-661,712-722` にあります。`HF_HOME` は CLI の `--data-dir` を置き換えず、pack の保存先にもなりません。

## 実行時の詳細

snapshot root の探索順は、設定されている `HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`HF_HOME/hub`、そして `Path.home() / ".cache" / "huggingface" / "hub"` です（`strata_control/drafting_fetch.py:76-85`）。Strata は各 root の下に `models--<repo名を slash から -- に置換>/snapshots/<pinned revision>` を組み立てます。

`_present()` は各 pinned ファイルについて候補 root を順に調べ、ファイルが存在し、期待サイズと SHA-256 の両方が一致した最初の候補を採用します。不一致や `OSError` の候補は採用せず、ほかの候補を続けて調べます（`strata_control/drafting_fetch.py:88-100,159-160`）。採用したファイルは Hub cache 内で変更・削除せず、pack 処理の入力にします。必要なファイルがそろわなければ通常の pinned download に進みます（`strata_control/drafting_fetch.py:160-179`）。

値は `ensure()` が探索 root を作るたびに読みます。Strata 側に `HF_HOME` の static cache はありません。探索時のログもありません。値が設定されていても snapshot が見つからなければ、それだけでエラーにはならず通常の download 経路になります。ネットワークが使えない場合は `DraftingError` となり、CLI は stderr に `strata: ...` を出して終了コード 5 を返します。Load は warning を通知し、上記の fallback で開始を続けます（`strata_control/drafting_fetch.py:161-162`; `strata_cli/drafting_cmd.py:116-123`; `strata_cli/launch/runner.py:1599-1606`）。

## 根拠

- `strata_control/drafting_fetch.py:76-85` — 変数の読み取り、候補 root の優先順、default root、snapshot path の組み立て。
- `strata_control/drafting_fetch.py:88-100,144-162` — cache の検証、ready pack の早期 return、snapshot 探索と download fallback。
- `strata_cli/drafting_cmd.py:81-123` — `plan` / `fetch` CLI の呼び出し条件と失敗時の出力・終了コード。
- `strata_cli/launch/runner.py:1581-1606` — Load 時の DFlash2 取得条件と失敗時の warning / fallback。
- `strata_control/drafting.py:648-661,712-722` — モデル・engine・backend・選択モードによる DFlash2 使用判定。

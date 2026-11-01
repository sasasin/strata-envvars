# `STRATA_NO_HANDOVER`

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。

## 役割

Terminal の起動時に、更新済みで現在のものより新しい Control が見つかった場合にそちらへ処理を引き継ぐ機能を止めます。strata.py の起動直後に評価され、真なら現在の Terminal がそのまま後続の preflight と CLI 処理へ進みます。これは Control への hand-over 制御であり、別の環境変数 STRATA_HANDOVER が示す「すでに hand-over 済み」のループ防止ガードとは別です。

## 値と判定

maybe_hand_over() は environ.get("STRATA_NO_HANDOVER") の Python 真偽値を使います。実プロセスの os.environ では、未設定なら None で偽、空文字なら偽、空でない文字列はすべて真です。文字列比較、数値変換、空白除去はありません。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | 偽 | 他の hand-over 条件を調べる |
| 空文字 "" | 偽 | 他の hand-over 条件を調べる |
| 任意の非空文字列（例: "1", "0", "false", " "） | 真 | maybe_hand_over() は直ちに None を返し、更新先を探さない |

既定値は実質 OFF（変数未設定または空文字では hand-over を無効化しない）です。CLI 引数による上書きはありません。STRATA_HANDOVER が真の場合も同じ早期 return になります。この二つの条件は or で評価されます（strata_cli/handover.py:22-24,126-133）。

## 有効になる条件

値が真のときは OS、インストール形態、Control の版、更新先の有無にかかわらず、maybe_hand_over() による引き継ぎを抑止します。ただし strata.py はその前に refuse_old_updater() を呼びます。この関数の分岐は STRATA_NO_HANDOVER を参照しないため、旧 updater の staged 起動を拒否する専用経路（条件に合えば stdout に案内を出して終了コード 7）までは抑止しません（strata.py:32-38, strata_cli/handover.py:174-187）。

偽の場合に hand-over が試されるのは、さらに STRATA_HANDOVER が偽で、ソース checkout からの起動を除外する条件に該当せず、active.json が指す Control の版が現在より新しく、その Control の interpreter と entry point がそろっている場合です。checkout は通常 hand-over を行いませんが、STRATA_HANDOVER_IN_CHECKOUT が設定されている場合、または maybe_hand_over() に明示 root が渡される場合は checkout 判定を通過します（strata_cli/handover.py:27-29,70-114,129-150）。

## 実行時の詳細

strata.py は maybe_hand_over() を依存の重い CLI import と _preflight() より先に呼びます。変数はその呼び出し時に毎回参照され、static/module cache はありません。したがって通常の起動ごとに判定されますが、同じプロセス内で後から環境を書き換えた場合に、この既に完了した hand-over 判定が再実行される経路はありません（strata.py:30-42, strata_cli/handover.py:126-141）。

無効化時は警告を出さず、元の引数で現在の Terminal が続行します。無効化されず、新しい Control への引き継ぎ条件が整った場合、Strata はその Control の bundled Python と strata.py を使い、元の CLI 引数を渡します。POSIX では execve でプロセスを置き換え、Windows では子プロセスを起動してその終了コードを返します。子環境には STRATA_HANDOVER=1 を設定して再 hand-over を防ぎ、Python 環境変数も調整します。起動に失敗した場合は stderr に "strata: could not start the updated Control ...; running ... instead." と警告し、現在の Terminal に戻ります（strata_cli/handover.py:117-123,148-163）。

## 根拠

- strata_cli/handover.py:22-24,126-133 — 環境変数名と truthiness による早期 return。STRATA_NO_HANDOVER=1 という説明コメント（同ファイル 10 行目）に対し、実装は "1" の完全一致ではなく、空でない値全般を真として扱います。
- strata.py:30-42 — 起動時の呼び出し順。hand-over / 旧 updater 拒否の後に preflight と CLI import を行います。
- strata_cli/handover.py:27-29,70-114 — checkout 判定、更新先 version の比較、更新先の完全性確認。
- strata_cli/handover.py:117-123,148-163 — 子環境、引数転送、POSIX/Windows の起動、警告と fallback。
- strata_cli/handover.py:174-187 — STRATA_NO_HANDOVER を参照しない旧 updater 専用拒否処理。
- docs/release-notes-0.2.2.md:51 — hand-over が Terminal に実装され、strata update 後の次回コマンドで新 Control を実行するというリリース説明。値の判定規則は実装を根拠としました。

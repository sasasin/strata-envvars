# `STRATA_SPLIT_ALLOW_UNTESTED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

strata launch の all-cards split engine 選択時に、実行実績のないカード数・カードアーキテクチャ・コンテキスト長を、選択ルールの不合格理由にしないための launcher 側フラグです。対象は strata_cli/launch/runner.py から strata_control.split_engine へ渡す判定だけで、split engine プロセスにはこの環境変数を設定しません。

このフラグは split engine を強制起動せず、OS、GPU 構成、モデル、メモリ、engine package、MTP など他の条件も緩和しません。自動選択（auto）にある別の適用制限も残ります。

## 値と判定

launcher は os.environ.get("STRATA_SPLIT_ALLOW_UNTESTED") == "1" を使い、文字列全体を "1" と完全一致比較します。値は数値変換されず、前後の空白除去や大文字小文字変換もありません。

| 環境変数の状態 | allow_untested |
| --- | --- |
| 未設定 | False |
| 空文字 | False |
| 1 | True |
| 0、true、yes、01、1 、その他の文字列 | False |

この判定を読む箇所は strata_cli/launch/runner.py:1546,1667 の 2 箇所です。strata_control/split_engine.py:203-219 では True の場合、カード数、カードアーキテクチャ、TESTED_CONTEXT を超える context を「未検証」として記録し、これらだけを理由に拒否しません。False なら通常どおり拒否理由に加えます。

## 有効になる条件

allow_untested=True が緩和するのは、strata_control/split_engine.py:203-219 の実行実績チェックだけです。次の条件は引き続き必要です。

- Linux、2〜4 枚、同一メーカー・同一カードモデル・同じ VRAM 容量であること。NVIDIA は compute capability 7.0 以上、AMD はビルド対象アーキテクチャであること（strata_control/split_engine.py:183-199）。
- 対応する routed expert tensor 型、48 層・512 experts のモデル形状、読める埋め込み等であること（同 :220-237）。
- 全 routed experts が VRAM に収まり、必要 RAM があること（同 :238-244）。
- all-cards 用 engine binary、モデルの MTP draft layer、draft_vocab_en.bin が見つかること（同 :493-507）。
- DFlash2 drafting、drafting off、独自 engine 引数、replicas、非 int8 の --kv など、split engine が扱わない設定がないこと（同 :461-474）。

カード数・アーキテクチャ・context の許可後も Auto モードの選別があります。NVIDIA は AUTO_SPLIT_BEATS_DFLASH2 にないカードでは Auto が拒否します（strata_control/split_engine.py:388-389）。AMD の Auto は AUTO_SPLIT_AMD_EXPERT_TYPES、AUTO_SPLIT_AMD_CARD_COUNTS、AUTO_SPLIT_AMD_ARCHS を満たす必要があります（同 :380-387）。従ってこの環境変数だけで、Auto が通常選ばない構成を強制することはできません。--split-engine on は別の opt-in であり、特に AMD では未検証アーキテクチャを試すための experimental_ok もコード上で有効にします（同 :421-423,484-487）。

split engine の mode は別判定です。STRATA_SPLIT_ENGINE が run config の split_engine（CLI の --split-engine が設定）より優先されます。ただし、STRATA_SPLIT_ALLOW_UNTESTED は mode の on/off を変更せず、CLI 引数と値を合成もしません（strata_control/split_engine.py:356-369）。

## 実行時の詳細

launcher は早い段階で split_expected() を呼んで、split engine を使う見込みなら Auto drafting を MTP として扱います。この見込み判定にも環境変数が渡されます。結果は runner インスタンスの _split_expected に保存され、以降の drafting 判定では再利用されます（strata_cli/launch/runner.py:1520-1549,1560-1562,2480-2488）。見込み判定内で例外が起きた場合は False として続行し、起動を止めません（同 :1547-1549; strata_control/split_engine.py:408-432）。

実際の設定作成では apply_split_engine() が環境変数をもう一度読み、SE.apply_to_config() に渡します（strata_cli/launch/runner.py:1617-1620,1630-1637,1662-1682）。したがって、初回の見込み判定は runner 内で cache されますが、最終判定は別の読み取りです。プロセス起動時に一度だけ固定する global cache はありません。通常の strata launch 実行中に環境が変われば、見込み判定と最終判定が異なる可能性があります。

許可された未検証条件は Decision.untested に記録され、split が選ばれれば通知に Using the all-cards split engine on N cards (…: not tested). の形で現れます（strata_control/split_engine.py:110-125,245-247、strata_cli/launch/runner.py:1676-1682）。他の条件を満たさず mode が auto の場合、拒否は quiet 扱いとなり通常の layer split を使います（strata_control/split_engine.py:435-448）。--split-engine on では拒否理由を通知し、launcher の例外経路も The all-cards split engine was left out (...). Using the normal layer split. と警告します（strata_cli/launch/runner.py:1668-1675）。選択後に split engine の起動が失敗したときも、server は失敗理由を [strata] The all-cards split engine could not start (...) と出し、通常の layer split を開始します（serve/server.py:9107-9145）。

環境変数は判定を行う Python launcher でのみ読みます。split config が子 engine 用に作る環境は元 config の env と FNX_ARENA / FNX_EXPERT_RAM_GIB から構成され、この変数を追加しません（strata_control/split_engine.py:250-270）。

## 根拠

- 候補一覧には名前があります（調査リポジトリ docs/envvars/000_envvers.md:1925）。Strata checkout 内の全参照は strata_cli/launch/runner.py:1546,1667 の 2 箇所で、どちらも Python の os.environ.get による直接読み取りです。helper 経由や別の動的な名前渡しはありません。
- 値判定と、未検証扱いになる対象: strata_cli/launch/runner.py:1546,1667; strata_control/split_engine.py:203-219,245-247。
- split engine の共通適用条件と mode / Auto 条件: strata_control/split_engine.py:183-199,220-244,356-389,461-507。
- 早期見込み判定と cache、実際の config 適用: strata_cli/launch/runner.py:1520-1549,1617-1682。
- 実行時の起動失敗 fallback: serve/server.py:9107-9145。
- docs/SPLIT_ENGINE.md:26-48,64-77 は auto/on の選択規則と未検証構成を説明しますが、この環境変数は記載していません。実際の許可挙動は上記コードに基づきます。

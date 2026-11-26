# `STRATA_SPLIT_ALLOW_UNTESTED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Terminal の all-cards split engine 判定で、通常は実行実績が条件に足りず拒否されるカード数、GPU アーキテクチャ、context 上限を通過させる。`strata launch` と `strata split-engine apply` が環境値を文字列 `"1"` と比較し、その真偽値を判定関数へ渡す。これは split engine を有効化するスイッチではなく、他の適合条件も緩和しない（`terminal/strata_cli/launch/runner.py:2241-2266`、`terminal/strata_cli/split_cmd.py:41-43`、`terminal/strata_control/split_engine.py:191-235`）。

## 値と判定

| 実行経路 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `strata launch` の事前判定と起動時判定、`strata split-engine apply` | `os.environ.get(...)` は `None` となり `False` | 文字列全体が厳密に `1` | 空文字、`0`、`true` / `TRUE`、`01`、`1 `、` 1` など。数値変換・trim・大文字小文字変換はしない |

Python の `os.environ.get("STRATA_SPLIT_ALLOW_UNTESTED") == "1"` の結果だけを使うため、未設定と空文字はともに許可しない。値が `"1"` でも、判定が有効になっている経路でのみ影響する（`terminal/strata_cli/launch/runner.py:2060,2266`、`terminal/strata_cli/split_cmd.py:43`）。

## 有効になる条件

- split engine のモードが `off` でないこと。モードは `STRATA_SPLIT_ENGINE` が run config の `split_engine` より優先し、CLI の `--split-engine` は run config を設定する。`off` なら対象変数を判定に使わず、`auto` / `on` で適合判定に進む（`terminal/strata_control/split_engine.py:435-448,522-526`）。
- 実行環境は Linux、または Windows 上の AMD HIP であること。カードは2枚以上かつ上限以下で、同一 vendor・同一モデル名・同一 VRAM 容量などの条件を満たす必要がある。古い NVIDIA 世代やビルド対象外の AMD アーキテクチャも許可されない（`terminal/strata_control/split_engine.py:199-215`）。
- `"1"` は、実績のないカード数、実績一覧にないアーキテクチャ、テスト済み上限を超えた context について拒否理由を `untested` の注記に変える。モデルの専門家テンソル形式・形状、VRAM/RAM の必要量など別の不適合理由は残る（`terminal/strata_control/split_engine.py:216-264`）。
- `auto` には追加ゲートがある。AMD は gfx1201・4枚・許可された expert type の組み合わせだけが自動対象で、NVIDIA は drafting が Auto の場合 compute capability 8.6 または 12.0 のカードだけが対象。この環境変数はこれらの自動選択条件を広げない（`terminal/strata_control/split_engine.py:50-60,456-469`）。
- `--split-engine on` の AMD 判定は `allow_untested` を内部で真にするため、同じ未テスト条件の許可にこの環境変数は不要。ただし AMD のビルド対象アーキテクチャ条件など、別のゲートは残る（`terminal/strata_control/split_engine.py:602-604`）。
- 許可された構成でも all-cards engine の実行ファイルが見つからない、draft layer / `draft_vocab_en.bin` がない、または他のモデル条件に合わない場合は起動しない（`terminal/strata_control/split_engine.py:607-635`、`terminal/strata_cli/launch/runner.py:2250-2259`）。

## 実行時の詳細

`strata launch` は `split_expected()` で Auto の drafting 計画にも判定結果を使い、初回の結果を Launcher インスタンスの `_split_expected` に保存する。ここで環境変数を読むのは cache miss 時の一度で、その後同じ Launcher 内での環境変更はこの事前判定に反映されない。一方、起動設定を書き立てる `apply_split_engine()` は別に環境値を読み直して `apply_to_config()` に渡す（`terminal/strata_cli/launch/runner.py:2016-2018,2033-2064,2070-2075,2241-2266`）。

判定では許可された未テスト条件を `Decision.untested` に記録する。条件を満たせば run config を all-cards split engine 用に書き換え、起動時に別の環境変数として転送する処理は確認できない（`terminal/strata_control/split_engine.py:123-140,267-290,635-639`）。Auto で拒否なら通常の layer split に静かに戻り、`on` なら理由の行を出す。起動時の例外も launch 自体を止めず通常の layer split に戻す（`terminal/strata_control/split_engine.py:516-530`、`terminal/strata_cli/launch/runner.py:2267-2281`）。

`strata split-engine apply` はコマンド実行時に環境値を読み、コピーした config に判定を適用する。成功時は `--out` 指定があれば変換後 config を書き、human 出力または JSON に `split`、`line`、`warn`、`reasons` などを返す。config の読み取り失敗は stderr（または JSON）のエラーで終了コード 5 になる（`terminal/strata_cli/split_cmd.py:25-58`）。

## ログと測定値

未テスト条件を通過して split が選ばれると、判定行は例えば `Using the all-cards split engine on 3 cards (3 cards: not tested).` の形で未テスト理由を含む。Terminal launch はこの行に ` Turn it off with: strata launch --split-engine off.` を追加する。通常の拒否は Auto では無言、`on` では通常 layer split にする理由を表示する（`terminal/strata_control/split_engine.py:135-140,527-528`、`terminal/strata_cli/launch/runner.py:2277-2281`）。この変数単独の性能測定値は Strata の資料に見当たらない。

## 根拠

- 全参照と環境値の受け渡し: `terminal/strata_cli/split_cmd.py:41-43`、`terminal/strata_cli/launch/runner.py:2033-2064,2241-2266`
- 未テスト判定と他の条件: `terminal/strata_control/split_engine.py:191-264,602-614`
- モード・config 書き換え・表示: `terminal/strata_control/split_engine.py:435-448,516-530,635-639`、`terminal/strata_cli/launch/runner.py:2267-2281`

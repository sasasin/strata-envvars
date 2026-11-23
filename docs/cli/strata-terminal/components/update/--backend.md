# `strata components update --backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | Engine family 名を取る文字列。例: `cuda`、`hip`、`sycl`、`metal`、`cpu`。GPU 名の別名と HIP variant 指定も受け付ける |

## 役割

この更新実行で対象とする Engine の backend を指定します。省略時は PC の検出結果などを使い、指定するとその backend を基準に Engine と、インストール済みのモデル形状別 Engine の更新パッケージを選びます。更新処理全体では Control も通常どおり更新対象ですが、Control の選択は OS platform によるため、この値では切り替わりません。

## 使い方

```sh
# 取得先 feed を読み、指定 backend なら何が対象になるかを確認する
strata components update --backend amd --check

# HIP の rdna2 variant を指定して更新する（パッケージ取得・検証・切替が発生し得る）
strata components update --backend hip-rdna2
```

`--check` はパッケージをダウンロードしませんが、feed の取得・検証を行い、確認結果を component ディレクトリの更新状態に保存します。

## 値と既定値

- parser は値を取る `--backend` を登録し、`choices`、型変換、既定値による選択制限を設定していません。省略時は `None` で、PC の検出結果が使われます（`terminal/strata_cli/update_cmd.py:47-56, 70-72`）。
- 指定値は前後の空白を除去して小文字化します。`nvidia` は `cuda`、`amd` は `hip`、`intel` と `arc` は `sycl` に対応します。`hip-<variant>` は family `hip` と variant `<variant>` に分けられます（`terminal/strata_control/engine_component.py:490-502`）。
- `hip-<variant>` の suffix に parser 段階の列挙チェックはありません。要求 variant と一致する候補があれば優先します。一致候補がなければ、その指定だけを理由に必ず失敗するわけではなく、適合候補の通常選択へ進みます（`terminal/strata_control/feed.py:757-780`）。
- 未知の文字列も parser では拒否されません。backend family としてその文字列が使われ、feed 内に適合するパッケージがなければ Engine は `none-for-this-pc` になります（`terminal/strata_cli/update_cmd.py:283-300`、`terminal/strata_control/feed.py:731-769`）。
- 値が空文字列の場合、実行側の条件分岐では指定なしとして扱われ、通常の hardware 検出へ進みます（`terminal/strata_cli/update_cmd.py:314-319`）。

## 実行時の動作

`strata components update` と `strata update` は共通の parser 登録関数を使います。実行時、値があれば `requested_hardware()` が backend を正規化し、認識済み family ならその値で hardware を検出します。認識されない値は検出済み hardware 情報にそのまま設定されます。指定値がない場合は通常の検出を使います（`terminal/strata_cli/update_cmd.py:59-79, 283-321`）。

この指定は一回の更新用で、設定ファイルへの保存処理はありません。省略時の検出では `STRATA_ENGINE_BACKEND`、保存済みの backend 選択、platform や GPU 情報などが使われます。明示した `--backend` は環境変数による検出を上書きし、`backend_source` が `requested` になるため、GPU vendor をまたがないための自動 `make_guard` は明示選択を拒否しません（`terminal/strata_control/engine_component.py:542-562`、`terminal/strata_cli/update_cmd.py:291-300`、`terminal/strata_control/updater.py:643-667`）。

Engine 候補は platform、backend、runtime、取得可能な GPU architecture 情報などで適合判定されます。適合候補から feed の版や build 条件を使って選び、既存 Engine の variant も考慮します（`terminal/strata_control/feed.py:731-789`、`terminal/strata_control/updater.py:670-719`）。同じ hardware 情報は、インストール済みのモデル形状別 Engine の候補選択にも使われます（`terminal/strata_control/shape_engine.py:266-273, 289-310`）。

通常更新では feed を一度読み、Engine、インストール済み形状別 Engine、Control の順に処理します。`--app` がある場合に限りアプリ更新も加わります。候補がない場合は Engine を更新せず、他の更新ステップは続けられます（`terminal/strata_control/updater.py:2044-2057, 2087-2116`）。Engine の取得は検証後、テスト起動を通してから切替える経路です（`terminal/strata_cli/update_cmd.py:59-79`、`terminal/strata_control/engine_update.py:405-425`）。

## 適用条件と副作用

- backend 候補は OS platform と組み合わせて照合されます。Strata が定義する family と platform の組み合わせは `terminal/strata_control/targets.py:22-31` にあります。指定した family / platform に適合する feed パッケージがないと、Engine は `none-for-this-pc` となります（`terminal/strata_control/feed.py:731-769`）。
- 明示 backend は意図的な選択として vendor 保護を通過します。インストール済み Engine と異なる GPU vendor を選べるため、異なる vendor 用 Engine が選択される可能性があります。実際の切替はパッケージ検証とテスト起動を通った後です（`terminal/strata_control/updater.py:643-667, 670-719`）。
- `--check` では Engine、Control、アプリの候補を報告し、候補パッケージはダウンロードしません。一方、feed の確認結果を `.updates/state.json` に保存します（`terminal/strata_control/updater.py:769-778`）。通常更新では更新状態やコンポーネントファイルが変更され、Engine の取得・検証・テスト起動が行われます（`terminal/strata_control/updater.py:2087-2116`）。
- 更新中のモデル停止・再起動は `--backend` ではなく、更新時のモデル gate と `--stop-model` / `--start-again` などで制御されます（`terminal/strata_cli/update_cmd.py:17-21, 67-79`）。

## 出力とエラー

未対応・未知の backend は parser の値エラーにはなりません。feed に適合する Engine がない場合、`--check` は候補なしの結果を表示します（`terminal/strata_cli/update_cmd.py:213-231`）。通常更新時も Engine が候補なしならその状態を結果に含め、処理全体は Control 等の別ステップを続行できます（`terminal/strata_control/updater.py:685-694, 2087-2107`）。

feed、署名、取得禁止などの失敗は `run()` の例外処理で人向けなら stderr、JSON / JSONL 出力なら JSON に出し、例外に対応する終了コードを返します。バックエンド指定が引き起こす個別の parser エラーや専用終了コードは確認できませんでした（`terminal/strata_cli/update_cmd.py:303-312, 374-386`）。

## 根拠

- parser 定義と `components update` への登録: `terminal/strata_cli/update_cmd.py:47-79`。
- 値の正規化、明示値と自動検出の分岐、hardware context の構築: `terminal/strata_cli/update_cmd.py:283-321`。
- alias、HIP variant、backend family 一覧、環境変数による通常検出: `terminal/strata_control/engine_component.py:490-502, 542-562`。
- family / platform 条件とパッケージ適合・選択: `terminal/strata_control/targets.py:22-31`、`terminal/strata_control/feed.py:731-789`。
- 更新時の vendor guard と backend に基づく候補選択: `terminal/strata_control/updater.py:643-719`。
- 通常更新の対象ステップと状態保存: `terminal/strata_control/updater.py:2087-2116`。

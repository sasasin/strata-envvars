# `strata components engines --backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 文字列。parser は選択肢を制限しない。engine family 名を指定する |

## 役割

導入済み engine の一覧で、「この PC に適合するか」と「どれが使用中か」を表示する際の backend family を指定します。省略時は PC の GPU から検出した backend を使います。`strata components engines` 自体は一覧を読むだけで、engine の切替・削除・ダウンロードはしません（`strata_cli/update_cmd.py:82-83,358-377`、`strata_control/engine_library.py:180-195`）。

## 使い方

```sh
strata components engines --backend hip
```

この例は HIP engine を基準に一覧の適合表示と使用中表示を計算します。出力形式は既定で人向けです。JSON が必要なら `--json` または `--output json` を指定できます（`strata_cli/update_cmd.py:47-56,363-377`、`strata_cli/cli.py:508-515`）。

## 値と既定値

- `--backend` は `_common()` が追加する通常の文字列引数で、`choices`、`type`、専用 validation はありません。省略時の parser 値は `None` です（`strata_cli/update_cmd.py:47-50,82-83`）。
- コマンド実行時にはまず `updater.detect_hardware()` が PC の platform・backend・GPU 情報を読み取り、その後、値が空でなければ指定値で `hardware["backend"]` を上書きし、`backend_source` を `requested` にします（`strata_cli/update_cmd.py:244-255`、`strata_control/updater.py:261-280`）。
- `split_backend()` は値を文字列化し、前後空白を除去して小文字化します。`hip-rdna2` のように `hip-` の後ろに文字がある値は backend `hip` と variant `rdna2` に分けられます。それ以外の名前はそのまま backend として扱われます（`strata_control/engine_component.py:465-471`）。
- `--backend ''` のような空値は `if a.backend` に入らず、未指定と同じく検出値を使います。空白だけの値は truthy ですが、正規化後は空文字列になります。この場合、一覧の適合判定では backend の絞り込みが実質行われません（`strata_cli/update_cmd.py:246-251`、`strata_control/engine_component.py:465-471`、`strata_control/engine_library.py:94-108,137-161`）。同じ option を複数回指定した場合は `argparse` の単一値引数として最後の値が残ります。
- family 名は engine の記録と一致する `cuda`、`hip`、`sycl`、`metal`、`cpu` などです。`nvidia` / `amd` / `intel` の別名変換はこの一覧処理では行われないため、記録上の `cuda` / `hip` / `sycl` と一致せず、適合表示の絞り込みに使えません（`strata_control/engine_component.py:465-482`、`strata_control/targets.py:23-29`、`strata_control/engine_library.py:63-67,151-161`）。

## 実行時の動作

handler は `lib.list_engines(ctx)` を呼びます。Qwen engine は指定 backend、platform、backend 対応表、必要に応じ GPU architecture・driver・runtime、ファイル整合性を使って `fits` と `why_not` を設定します。DeepSeek engine は platform と backend の一致を使います。指定 backend に合わない engine は「この PC 向けではない」と表示されます（`strata_control/engine_library.py:59-81,91-111,136-162`）。

使用中表示の判定にも backend が渡ります。Qwen engine は `ec.resolve(..., backend=wanted)` が選ぶものを active とし、未選択なら active なしとして扱います。`hip-rdna2` の variant 部分は `variant_wanted` に保存されますが、engine 一覧側はそれを参照せず、`hip` family として判定します。variant を一覧の絞り込み条件にする動作は確認できません（`strata_cli/update_cmd.py:246-251`、`strata_control/engine_library.py:91-111,137-161`、`strata_control/engine_component.py:1012-1045`）。

このコマンドは `_common()` の他の共通 option も parser 上は受け付けますが、`engines` 分岐は feed 読込・更新処理より前に一覧 handler へ戻ります。`--feed`、`--force`、`--model-config` はこの分岐で参照されず、`--wait` も一覧処理では使われません（`strata_cli/update_cmd.py:47-56,272-284,358-377`）。`--components-dir` は列挙対象の component folder を変更します（`strata_cli/update_cmd.py:244-245`）。

## 適用条件と副作用

- `strata components engines` はネットワーク更新・ファイル変更を行いません。導入済み package の scan、サイズ計算、互換性・整合性確認を行い、engine 使用中判定のため process 使用状況も確認します（`strata_control/engine_library.py:91-111,136-195`）。
- 指定値が未知でも parser error にはなりません。backend が記録された engine は family 不一致で `fits: false` になります。DeepSeek の backend が空の項目は backend 不明として適合表示を維持します（`strata_control/engine_library.py:63-67,151-161`）。
- `--backend` は一覧の評価条件だけを変え、PC の保存設定や環境変数を書き換えません。`STRATA_ENGINE_BACKEND` は先行する hardware 検出には影響し得ますが、非空の CLI 値がその後 `hardware["backend"]` を上書きします。環境変数の値自体が検出段階でどう扱われるかは [`STRATA_ENGINE_BACKEND`](../../../../envvars/STRATA_ENGINE_BACKEND.md) を参照してください（`strata_control/updater.py:261-280`、`strata_cli/update_cmd.py:246-251`）。

## 出力とエラー

人向け出力は engine ごとに version、サイズ、backend/variant、`in use` / `newest` / `not for this computer` のタグを表示し、適合しない場合は理由も表示します。最後に `use` と `remove` の案内と「Nothing was changed.」を出します。`--json` / `--output json` は一覧データを JSON で出力します（`strata_cli/update_cmd.py:363-377`）。

この handler に backend 名専用のエラー経路はありません。parser は未定義の名前を拒否せず、一覧結果の適合判定に反映します（`strata_cli/update_cmd.py:47-50,358-377`、`strata_control/engine_library.py:63-67,151-161`）。

## 根拠

- parser、既定値、共通 option: `strata_cli/update_cmd.py:47-56,82-83`
- handler dispatch と一覧出力: `strata_cli/update_cmd.py:244-255,272-284,358-377`
- backend 指定の正規化と hardware 検出: `strata_control/engine_component.py:465-471`、`strata_control/updater.py:261-280`
- engine の適合・active 判定、読み取り専用一覧生成: `strata_control/engine_library.py:59-81,91-111,136-195`
- `resolve()` の backend 選択: `strata_control/engine_component.py:1012-1045`
- backend family と OS 対応表: `strata_control/targets.py:20-29`
- 調査制約: 対象は上記ソース checkout の parser と処理経路です。別途ビルドされた CLI help、Release archive の実体、および各 OS / GPU 環境での実行結果は確認していません。

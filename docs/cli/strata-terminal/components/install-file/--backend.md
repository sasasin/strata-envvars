# `strata components install-file --backend`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend 名を表す文字列。現在の既知 family は `metal`、`cuda`、`hip`、`sycl`、`cpu`。parser は選択肢や型変換を指定しない（既知 family: `strata_control/targets.py:23-29`） |

## 役割

ローカルの engine package を導入するとき、PC の自動検出結果に代えて、package 適合判定に使う backend family を指定します。package 自体は位置引数 `file` で指定します。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --backend hip
```

## 値と既定値

`--backend` は共通 parser `_common()` が `default=None` で登録し、`choices`、`type`、独自 validator はありません。省略時は `updater.detect_hardware()` の検出結果を使います。値を指定すると `engine_component.split_backend()` が前後の空白を除去し、小文字化します。`hip-<名前>`（`<名前>` が空でない場合）は `("hip", "<名前>")` に分解され、それ以外は名前をそのまま family として扱います。

値が空文字列なら `run()` の `if a.backend` が成立しないため、CLI 指定値としては適用されず、検出結果が使われます。未知の family も parser 段階では拒否されませんが、通常は package の backend と一致せず、適合判定エラーになります。

## 実行時の動作

`strata components install-file` は update command の共通 option 群を登録し、`--backend` を受け付けます。parser は `strata_cli/cli.py` から登録され、実行時に `update_cmd.run()` へ委譲されます（`strata_cli/update_cmd.py:37-47,66-69`; `strata_cli/cli.py:139-140,2135-2137`）。

`run()` はまず現在の hardware 情報を検出し、`--backend` が空でない場合は検出した `hardware["backend"]` を指定 family で置き換え、`backend_source` を `requested` にします（`strata_cli/update_cmd.py:194-202`）。`hip-rdna2` のような値では family が `hip`、variant が `rdna2` になります（`strata_control/engine_component.py:439-445`）。

install-file 経路は feed を読まず、位置引数の archive を展開して署名と全ファイルを検証した後、package と hardware の適合性を検査します（`strata_cli/update_cmd.py:219-228`; `strata_control/updater.py:1162-1206`）。適合判定では OS platform と backend family が比較され、CUDA/HIP では検出できた GPU architecture、CUDA では読み取れた driver version、package が要求する runtime version も確認されます（`strata_control/feed.py:408-431`）。

`hip-<variant>` の suffix は hardware 情報の `variant_wanted` に格納されますが、この install-file 経路が呼ぶ `engine_fit_reasons()` はその値や package の variant 名を照合しません。したがって、このオプションで `hip-rdna2` を指定しても、この経路では `hip` family を指定した効果までで、`rdna2` という variant の一致は検証しません（`strata_cli/update_cmd.py:197-202,223`; `strata_control/updater.py:1204-1206`; `strata_control/feed.py:408-431`）。GPU architecture が読み取れない場合、HIP package の architecture 適合判定は拒否理由を返しません（`strata_control/feed.py:401-405,426-427`）。

## 適用条件と副作用

- このオプションが作用するのは `strata components install-file` の backend 適合判定です。`--feed` はこの install-file 分岐では参照されず、指定した package の取得元を変えません（`strata_cli/update_cmd.py:219-229`）。
- 指定した family が package と異なる場合や、検出済み GPU architecture / driver / runtime 条件に合わない場合、package は拒否されます。package 適合後は通常の test-start と engine 切り替え処理に進みます（`strata_control/feed.py:408-431`; `strata_control/updater.py:1204-1219`; `strata_control/updater.py:1068-1079`）。
- CLI が指定値を使うと hardware family が上書きされるため、package の適合判定は検出された GPU family ではなく指定 family に対して行われます（`strata_cli/update_cmd.py:196-202`）。

## 出力とエラー

正常終了時は human 出力で導入結果を表示し、`--output json` / `--json` または `--output jsonl` では JSON を出します（`strata_cli/update_cmd.py:185-192,223-228`; `strata_cli/cli.py:508-515`）。package が現在の PC に適合しない場合など `UpdateError` は `strata:` 付きで stderr に出力され、エラーに設定された終了コード（適合拒否は 5）を返します（`strata_control/updater.py:1204-1206`; `strata_cli/update_cmd.py:187-192,257-258`）。

## 根拠

- `strata_cli/update_cmd.py:37-47,66-69` — 共通 parser option と install-file parser の登録。
- `strata_cli/update_cmd.py:194-202,219-228,257-258` — 検出結果の上書き、install-file への分岐、出力と UpdateError 処理。
- `strata_cli/cli.py:139-140,2135-2137,508-515` — parser 登録、update command への委譲、one-shot command の `--json` / `--quiet` 追加。
- `strata_control/engine_component.py:439-445` — backend 名と HIP variant suffix の分解。
- `strata_control/targets.py:20-29` — 現行の既知 backend family。
- `strata_control/updater.py:1162-1222` — ローカル archive の検証、適合判定、導入処理。
- `strata_control/feed.py:401-431` — hardware と package の適合条件。variant 名自体はこの判定で照合されない。

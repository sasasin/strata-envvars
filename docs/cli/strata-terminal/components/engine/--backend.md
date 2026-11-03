# `strata components engine --backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata checkout は `main` = `origin/main`、作業ツリー clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend family 名の文字列。parser に `choices` や型変換はなく、既定値は `None` |

## 役割

ローカル component folder にある engine package のうち、指定した backend を使う場合にこの PC で起動可能なものを照合し、選ばれる engine を表示します。このコマンドは起動可能性の確認だけを行い、ダウンロードやファイル変更はしません（`strata_cli/cli.py:132-138,2015-2042`）。

## 使い方

```sh
strata components engine --backend cuda
strata components engine --backend hip --components-dir ./strata-components --full --output json
```

`--backend` を省略すると PC の backend を検出します。`--components-dir` は調べる component folder、`--full` は全ファイルの hash 検査、`--output` は `human`（既定）または `json` を選びます（`strata_cli/cli.py:132-138`）。

## 値と既定値

- parser は値を必須引数として受け取りますが、backend 名の choices、case 正規化、alias 変換は宣言していません（`strata_cli/cli.py:134`）。
- `None`（未指定）なら `engine_component.resolve()` が `detect_backend()` の結果を使います。検出できなければ CPU backend を選びます（`strata_control/engine_component.py:1021-1027`）。
- backend matrix にある family は `metal`, `cuda`, `hip`, `sycl`, `cpu` です。matrix 上の対象 platform は `strata_control/targets.py:20-29` に定義されています。`nvidia` / `amd` / `intel` / `arc` の alias 変換は `launch --backend` の設定保存用 helper にあり、この `components engine` 経路では呼ばれません（`strata_control/engine_component.py:474-482`, `strata_cli/cli.py:2021`）。
- `--backend ''` のような空文字列も parser では拒否されません。空文字列は `None` ではないため検出に切り替わらず、空 family として package に照合され、通常は利用可能な engine が見つからない結果になります（`strata_cli/cli.py:134,2021`; `strata_control/engine_component.py:1021-1027,1043-1045`）。
- 未知の family も parser では受理されますが、matrix にない package family は照合時に利用不可になります（`strata_control/targets.py:44-48`; `strata_control/engine_component.py:1039-1045`）。

## 実行時の動作

1. `--components-dir` があればその path を使い、省略時は `STRATA_COMPONENTS_DIR` または OS ごとの per-user component folder を使います（`strata_cli/cli.py:135-136,2019`; `strata_control/engine_component.py:176-190`）。
2. `status()` は `<components>/engine` を走査して manifest を読み、platform と backend、runtime、GPU architecture、NVIDIA driver 条件などを照合します。既定の quick check では hash 対象が entrypoint だけで、`--full` を指定すると全 package file を検証します。署名と integrity の検証に失敗した package は選択対象になりません（`strata_control/engine_component.py:933-946,1012-1071`; `strata_cli/cli.py:137,2021`）。
3. 指定 backend が適用されるのは package family の選別です。OS が matrix で未対応の組み合わせは拒否されます。複数の package が使えるとき、利用可能な pin があればそれを優先し、そうでなければ version、driver 要件、AMD / CUDA architecture の順に比較して一つを選びます（`strata_control/targets.py:20-29`; `strata_control/engine_component.py:1035-1045,1090-1097`）。
4. `--backend` 自体は設定保存や永続化をしません。`status()` は読み取り用の report を組み立て、cached update notice もローカル state から読みます（`strata_control/engine_component.py:1122-1142,202-211`）。

## 適用条件と副作用

- 指定した family がこの PC の実 GPU と一致する必要はありません。指定値は照合 family として使われ、backend が違う、platform 非対応、GPU architecture が合わない、最低 driver/runtime を満たさない package は利用不可になります（`strata_control/engine_component.py:1035-1063`; `strata_control/targets.py:44-50`）。
- family 名に variant を付ける構文（例 `hip-rdna2`）をこのコマンドは分解しません。分解処理 `split_backend()` は別の更新・launch 経路で使われていますが、`components engine` は `status(..., backend=a.backend)` にそのまま渡します（`strata_control/engine_component.py:465-471`; `strata_cli/cli.py:2021`）。
- `--full` の有無にかかわらず、backend 検出時には環境変数の選択、保存済み選択、platform 判定、OS の GPU 情報や既存の検出ツールが参照され得ます。検出は read-only とされ、既存の `nvidia-smi` / `rocminfo` / `hipInfo` / `sycl-ls` を最大 8 秒で呼び出す分岐があります（`strata_control/engine_component.py:514-560`）。
- コマンドは engine を起動せず、ネットワークにも接続せず、何も変更しない旨を human 出力にも明記します（`strata_cli/cli.py:2015-2042`）。

## 出力とエラー

- 成功時は human 出力で component folder、検出または指定した backend、installed package、選択 engine を表示します。JSON 出力は `schema_version: 1`、`ok`、report fields を stdout に出します（`strata_cli/cli.py:2024-2041`）。
- 条件に合う engine がない場合は `usable=false` と理由 notice を report に含め、human では stderr に notice、JSON では `ok:false` の JSON を stdout に出し、終了コード 5 を返します（`strata_cli/cli.py:2024-2037`; `strata_control/engine_component.py:70-88,1122-1142`）。
- `--backend` を省略した自動検出経路で `ComponentProblem`（例: backend 検出環境変数が不正）が発生すると、CLI は stderr の `strata: ...` または JSON error を出して終了コード 2 を返します。明示値がある場合は `status()` 内の検出例外は記録されますが、package の照合には明示値が使われます（`strata_control/engine_component.py:518-522,1122-1129`; `strata_cli/cli.py:2021-2023,527-532`）。
- 引数値自体の family validation はありません。未知値は通常 parser error ではなく、利用可能 engine がない照合結果（終了コード 5）になります（`strata_cli/cli.py:134,2021-2024`; `strata_control/engine_component.py:1039-1045`）。

## 根拠

- Parser・option scope: `strata_cli/cli.py:132-140`
- Report、終了コード、human / JSON 出力: `strata_cli/cli.py:2015-2042`
- backend matrix: `strata_control/targets.py:20-29,44-50`
- component folder の既定値: `strata_control/engine_component.py:176-190`
- backend family の選択・自動検出: `strata_control/engine_component.py:465-482,514-560,1012-1027`
- package の適用条件・検証・選択順位: `strata_control/engine_component.py:933-946,1035-1097`
- status report と欠落時の扱い: `strata_control/engine_component.py:70-88,1122-1142`

調査制約: ソースコードを対象にし、CLI `--help`、Release artifact、実 GPU / backend の実動作は確認していません。backend ごとの外部 driver / tool の挙動は Strata の実装範囲を超えるため記述していません。

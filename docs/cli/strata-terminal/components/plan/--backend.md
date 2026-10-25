# `strata components plan --backend`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components plan` |
| オプション | `--backend BACKEND` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/components.py`、`strata_control/targets.py` |

このオプションは、指定した component manifest の backend と照合する backend family を指定します。単独では component を取得・展開・有効化しません。

## 利用例

```sh
strata components plan ./engine-manifest.json --backend cuda
```

## 値と既定値

- `BACKEND` は値必須の文字列です。parser は `choices` や型変換を設定しておらず、backend 名の候補を CLI 層では制限しません。省略時は `None` です（`strata_cli/cli.py:120-128`）。
- この値は、manifest の `backend` が指定されている場合にのみ比較に使われます。manifest の backend と異なる値なら非互換理由が追加されます。manifest に backend がない場合、指定値による比較は行われません（`strata_control/components.py:208-228`）。
- `--backend` の値そのものを OS/backend 対応表で検証するのではなく、manifest に記録された backend が対象 platform でサポートされるかも別途確認します。そのため未知の値でも parser では拒否されず、manifest 側の backend があれば比較不一致として扱われます。manifest 側の backend がない場合、この値は互換性判定に影響しません（`strata_control/components.py:221-227`、`strata_control/targets.py:20-29,42-51`）。

## 実行時の動作

1. `manifest` のパスを読み、JSON component manifest として厳密に解析します。manifest の backend は `backend` フィールドから読み込まれます（`strata_cli/cli.py:1973-1980`、`strata_control/components.py:136-161,200-205`）。
2. `--target` が別途指定されていればその platform key、なければ現在のホスト platform を判定対象にします。その target と `--backend` を `check_compatible` に渡します（`strata_cli/cli.py:1982-1983`）。
3. 判定では manifest の platform 一覧、指定された backend との一致、manifest 自身の backend と target の対応可否を調べ、理由の一覧を作ります（`strata_control/components.py:208-228`）。`--backend` は backend を自動検出する指定ではなく、manifest に書かれた backend と比較する値です。
4. 成功時は component の識別情報、manifest backend、target、互換可否と理由、artifact 情報、合計サイズ、requires、entrypoint を表示します（`strata_cli/cli.py:1984-2011`）。`--output json` は `schema_version: 1` と `ok: true` を含む JSON を出力します。非互換の場合も JSON の `usable` が `false` になり `reasons` に説明が入ります（`strata_cli/cli.py:1984-1995,535-542`）。

## 適用条件と副作用

- `--target` を併用すると、backend と platform の組み合わせを指定 target に対して確認します。省略時の target は `host_platform()` が生成する OS-architecture key です（`strata_cli/cli.py:125-127,1982-1983`、`strata_control/targets.py:31-39`）。
- backend の対応可否は manifest に記録された backend について確認されます。対応表では Metal は macOS arm64、CUDA/HIP は Windows または Linux x86_64、SYCL は Linux x86_64、CPU は列挙された macOS/Windows/Linux の各 architecture が対象です（`strata_control/targets.py:20-29,42-51`）。
- このコマンドは読み取り専用です。処理内で manifest を読み、互換性を判定して結果を表示します。出力の末尾にも「何もダウンロード、展開、変更していない」と表示します（`strata_cli/cli.py:1974-1983,2010`）。
- `--backend` は `strata components engine --backend` など同名オプションとは別 scope です。こちらでは manifest の互換性照合に使われ、ローカル engine 選択を行うものではありません（parser: `strata_cli/cli.py:120-128,132-138`、処理: `strata_cli/cli.py:1966-2011,2014-2023`）。

## 出力とエラー

- manifest パスが存在しない場合は `no component manifest at ...` を出し、終了コード `2` です（`strata_cli/cli.py:1974-1976`）。
- JSON 不正、必須項目不足、未知の component kind、artifact や platform の不正など `ComponentError` になる manifest はエラーとして返されます。`ComponentError` の既定コードは `6` です（`strata_control/components.py:136-205`、`strata_control/targets.py:12-17`）。
- `--output json` 指定時の明示的なエラーは `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` 形式、それ以外は stderr に `strata: ...` 形式です（`strata_cli/cli.py:527-532`）。読み込み時の `OSError` は共通の例外処理でコード `6` のエラーになります（`strata_cli/cli.py:2176-2183`）。
- 互換性がない場合も互換性判定自体は正常に完了し、human 出力で `usable NO` と理由を表示して終了コード `0` を返します。JSON も envelope の `ok` は `true` で、可否は `usable: false` で示します（`strata_cli/cli.py:1984-2011,535-542`）。

## 関連文書

- [`strata components plan` のコマンド概要](README.md)
- [`--target`](--target.md)
- [`--output`](--output.md)
- [CLI オプション索引](../../../README.md)

## 根拠

- `strata_cli/cli.py:120-128` — `components plan` parser と `--backend` の既定値・引数指定。
- `strata_cli/cli.py:1966-2011` — manifest 読込、互換性判定、human/JSON 出力、読み取り専用の表示。
- `strata_cli/cli.py:527-542,2119-2183` — 共通の成功・失敗出力、終了コード処理。
- `strata_control/components.py:136-205` — manifest の解析と backend/platform 項目の取得。
- `strata_control/components.py:208-228` — platform/backend の互換性判定。
- `strata_control/targets.py:12-17,20-51` — component エラーコード、backend 対応表、target 判定。

# `strata tune auto --allow-small-differences`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--allow-small-differences` |
| 別名 | なし |
| 値 | 値なしのフラグ。省略時 `false`、指定時 `true` |

## 役割

自動チューニングで、設定によって回答がわずかに変わる可能性がある候補も測定対象に含めます。通常は回答が標準設定とバイト単位で同一になる候補だけを自動選択し、このフラグは CPU/GPU への処理配置などが変わり、回答差が生じ得る `placement` 分類の候補を許可します。フラグ自体が設定を即時変更したり、候補の採用を保証したりするものではありません（`strata_control/tune_knobs.py:12-14,353-356`）。

## 使い方

```sh
strata tune auto <profile名または実行設定JSON> --allow-small-differences
```

たとえば保存済み profile `work` を対象にする場合:

```sh
strata tune auto work --allow-small-differences
```

`target` は保存済み profile 名または実行設定 JSON です（`strata_cli/tune_commands.py:20-26`）。

## 値と既定値

値は取りません。parser は `action="store_true"` で定義されているため、省略時は無効、指定時に有効です。後ろに値を付ける形式ではありません（例: `--allow-small-differences true` はこのオプションの構文ではありません）。短縮別名はありません（`strata_cli/tune_commands.py:33-34`）。

## 実行時の動作

`strata tune auto` の実装はフラグを `Options.allow_placement` に渡し、設定から作る tuner context に反映します（`strata_cli/tune_commands.py:193-197`; `strata_control/autotune.py:50-68,850-897`）。候補選別時、`placement` 分類はこの値が真の場合に限って許可されます。無効なら候補をスキップし、「回答がわずかに変わる可能性があるため許可が必要」という理由を記録します（`strata_control/tune_knobs.py:337-356,380-417`）。

この許可が影響する候補は、モデル系列、backend、マシンクラス、チューニング目標、必要なハードウェア条件、`--mode` などでも絞られます。現行候補表では、expert cache の調整、speculative window、PCIe 配分、Qwen 3.6 系の draft window・prompt chunk・hybrid row block などが `placement` 分類です。従ってフラグを指定しても、対象 PC や設定に合う候補がなければ追加候補は実行されません（`strata_control/tune_knobs.py:80-111,189-227,230-243,380-417`）。候補ごとに基準設定から単一 knob を変え、測定後に性能条件を満たすものだけが勝者になります（`strata_control/tune_knobs.py:55-77`; `strata_control/autotune.py:437-558`）。

チューニングは実エンジンを起動して測定するため、許可された候補がある場合は追加のエンジン実行と計算負荷が発生します。候補を試す前にもメモリ等の guard があり、条件に合わない候補はスキップされます（`strata_control/autotune.py:15-18,471-500`）。結果が改善または標準設定の確認となり、かつ `--no-save` が指定されていない場合は preset を作成します。試行履歴の記録は別に行われ、I/O error は握りつぶされます（`strata_cli/tune_commands.py:240-250`）。このフラグだけで現在の profile を直接書き換える処理はありません。

## 適用条件と副作用

- `strata tune auto` 専用です。トップレベルや別コマンドの同名引数としては登録されていません（`strata_cli/cli.py:486-489,1652-1653`; `strata_cli/tune_commands.py:20-35`）。
- 有効になるのは `placement` 分類の候補選別だけです。回答が再現不能な候補を許可する `--allow-not-repeatable` とは別の制御です（`strata_cli/tune_commands.py:33-35`; `strata_control/tune_knobs.py:353-356,410-413`）。
- 分類の説明は「同じ計算だが CPU/GPU の分割が異なるため、僅差の判定が逆転し得る」です。候補が採用された場合、標準設定と回答が完全一致するとは限りません（`strata_control/tune_knobs.py:12-14,26-32`）。
- チューナーが改善を確認して preset に保存する場合があります。保存しない測定には `--no-save` を併用できます（`strata_cli/tune_commands.py:38,246-250`）。

## 出力とエラー

このフラグ固有の警告やエラー処理は定義されていません。値を伴わせるなど parser が受け付けない構文では、CLI の argparse が引数エラーとして扱います。チューニング中の通常進捗は human 出力では stderr に出され、最終結果は human または JSON で出力されます（`strata_cli/tune_commands.py:95-108,205-215,257-261`）。候補がスキップされた理由は tuner の結果に記録されます（`strata_control/tune_knobs.py:396-417`）。

## 根拠

- parser と既定動作: `strata_cli/tune_commands.py:20-46`
- CLI からの dispatcher: `strata_cli/cli.py:486-489,1652-1653`
- 値の `Options` / `Context` への引き渡し: `strata_cli/tune_commands.py:193-197`; `strata_control/autotune.py:50-68,850-897`
- 回答クラス、許可判定、候補条件: `strata_control/tune_knobs.py:12-14,80-111,189-227,230-243,337-356,380-435`
- 候補の測定と性能判定: `strata_control/autotune.py:437-558`
- 出力、preset 保存と終了コード: `strata_cli/tune_commands.py:95-108,205-215,230-261`

調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されませんでした。Release artifact や各 backend を実行しての挙動確認は行っておらず、本書は上記 revision のソース調査に基づきます。

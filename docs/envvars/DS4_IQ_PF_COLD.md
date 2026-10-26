# `DS4_IQ_PF_COLD`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 の IQ 形式 expert を CPU lane で計算するとき、ファイル mapping 上の expert 行列に対する prefetch hint の出し方を選びます。未設定または数値として 0 になる値では、対象範囲すべてに `os::prefetch()` を呼びます。0 以外では `os::prefetch_cold()` を呼び、Windows では既に resident と判定された範囲を prefetch 対象から外します。

これは CPU lane の expert 行列を読む前の OS 向け hint の選択です。計算結果や expert の選択はこの変数で変わりません。非 Windows では両方の helper が同じ範囲に prefetch hint を出すため、この変数による動作差はありません。

## 値と判定

`cpu_experts_iq()` 内の `static const bool` として初回に一度だけ判定します。実装は `getenv()` と `atoi()` を使い、真偽文字列として parse しません。

| 値 | `pf_all` | 選択される処理 |
|---|---:|---|
| 未設定 | true | 全対象範囲へ `os::prefetch()` |
| 空文字 | true（`atoi` が 0） | 全対象範囲へ `os::prefetch()` |
| `0`、`00`、` 0x`、数字で始まらない文字列 | true（変換値 0） | 全対象範囲へ `os::prefetch()` |
| `1`、`-1`、`2tail` など、`atoi` の結果が 0 以外 | false | `os::prefetch_cold()` |

`atoi` は先頭の空白と符号を許し、先頭から変換できる数字までを読みます。後続文字列は変換結果に含まれません。従って `1tail` は 1、`tail1` は 0 です。範囲外の数値を渡した場合の結果は C の `atoi` の範囲外動作に従い、このコードでは別途検査・fallback しません。値は初回判定後キャッシュされるため、その後プロセス環境を書き換えても再評価されません。

## 有効になる条件

- IQ 形式の expert が CPU lane で処理され、`cpu_experts_iq()` に到達したときに評価されます。`cpu_experts_mx()` は `gg::mx_experts()` が false の場合にこの関数へ進みます。
- 各 expert の行列を prefetch 候補に加えるのは `!store` かつ、その expert が RAM tier にない場合（`l.ram` が空、または expert の RAM slot が負）です。候補には gate / up / down の3行列が含まれます。
- Windows で `DS4_IQ_PF_COLD` が 0 以外の場合、`DS4_PF_ALL` が別途 0 以外なら `prefetch_cold()` の Windows 専用設定が全範囲 prefetch に切り替えます。この `DS4_PF_ALL` も helper 内の static 値として一度判定されます。
- Windows 以外では `prefetch_cold()` が `prefetch()` をそのまま呼ぶため、どの値でも実質同じ hint になります。

## 実行時の詳細

候補範囲を作成した後、`DS4_IQ_PF_COLD` の判定に従って同期的に helper を呼び、その後に activation の量子化と CPU expert 計算へ進みます。Windows の `prefetch_cold()` は範囲ごとに最大8点を sampling し、全点が resident と確認できた範囲を除外して `PrefetchVirtualMemory` の対象にします。sampling に失敗した範囲も prefetch 対象に残ります。`DS4_PF_ALL` が有効なら sampling を行わず全範囲を prefetch します。非 Windows の `prefetch()` は各範囲に `madvise(..., MADV_WILLNEED)` を呼びます。

この経路自体に環境変数値や prefetch 成否を出すログはありません。`PrefetchVirtualMemory` や `madvise` は best-effort hint として実装され、戻り値を判定して処理を変えることもありません。

## 文書・測定との照合

ソースコメントは `DS4_IQ_PF_COLD=1` で cold prefetch を選べると説明しています。実装上は `atoi` の結果が 0 以外なら選択されるため、`1` に限定されません。またコメントに「off by default」とありますが、変数 unset 時の実装は `pf_all=true` であり、off になるのは `prefetch_cold()` 側です。`docs/DETAILS.md` と関連文書にはこの変数固有の挙動や測定値の記載を確認できませんでした。

## 根拠

- `src/dsv41/ds4_model.cu:5639-5640` — MX expert 判定後に IQ CPU lane へ分岐。
- `src/dsv41/ds4_model.cu:5728-5753` — IQ CPU lane の prefetch 候補、環境変数判定、helper 選択。
- `src/dsv41/ds4_os.hpp:307-325` — `prefetch()` の Windows / 非 Windows 実装。
- `src/dsv41/ds4_os.hpp:346-389` — resident sampling と `prefetch_cold()`、`DS4_PF_ALL` の上書き。

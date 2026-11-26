# `PROCESSOR_ARCHITECTURE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows installer では、`PROCESSOR_ARCHITEW6432` が PowerShell 上で falsy のときにこの値を読み、`AMD64` 以外ならインストールを停止する。Strata Control の Windows machine 判定では、優先環境変数 `PROCESSOR_ARCHITEW6432` が空または空白の場合の代替値となり、`sysinfo.machine()` を通じてホスト platform とエンジン対象の判定に使われる。Linux/macOS ではこの判定関数は参照しない。`app/host/server/agent/harness-runtime.mjs` の allowlist にも名前があるが、そこでは値を解釈せず Harness 子プロセスへ環境を渡す対象にしているだけである。 (`tools/packaging/install.ps1:100-106`, `terminal/strata_control/sysinfo.py:55-78`, `terminal/strata_control/targets.py:33-45`, `app/host/server/agent/harness-runtime.mjs:20-36,75-83`)

## 値と判定

| 条件 | unset / 空文字 | 有効になる値（例） | それ以外の値（例） |
|---|---|---|---|
| Windows の `sysinfo._windows_machine()`。ただし `PROCESSOR_ARCHITEW6432` が先に非空であれば本変数は参照されない | `.get(key, "")` の結果を strip し、空なら `_WINDOWS_MACHINES` による変換へ進まず、Python の `sysconfig.get_platform()` を使う fallback へ進む | `amd64`、`x86_64`、`arm64`、`aarch64`、`x86`、`i386`、`i686`、`ia64` は前後空白除去後、大文字小文字を無視してそれぞれ `AMD64`、`ARM64`、`x86`、`ia64` へ正規化 | 空白だけも空として扱う。未登録文字列 `value` は前後空白だけ除いて原文の大文字小文字を保ったまま返す。数値 parse や妥当性検査はしない |
| Windows `tools/packaging/install.ps1`。スクリプトは feed と Windows OS を確認した後に評価 | `PROCESSOR_ARCHITEW6432` が PowerShell の falsy 値なら本変数を選ぶ。両方 unset/空なら `$arch` は空となり、`AMD64` 以外として停止 | `$arch -ne 'AMD64'` が偽になる `AMD64`。PowerShell の通常の文字列比較は大文字小文字を区別しない | `ARM64` や空など `AMD64` と等しくない値は停止。比較は数値変換ではなく文字列比較 |
| agent 環境 allowlist | 変数が base environment に無ければコピーされない | 名前が `KEEP` 正規表現に一致するため、`externalEnvironment(base)` に含まれ、値が undefined でなく、secret-name regex に当たらなければ値を保持 | 値自体の形式・空文字を検査しない。Strata はこの経路で architecture 判定をしない |

Control 側では `PROCESSOR_ARCHITEW6432` が先に調べられ、strip 後に非空ならその値が採用されて `PROCESSOR_ARCHITECTURE` は読まれない。Windows 以外では `machine()` は `platform.machine()` を返す。 (`terminal/strata_control/sysinfo.py:55-78`)

## 有効になる条件

- `tools/packaging/install.ps1` の Windows installer 経路で、`STRATA_FEED` が指定され、OS が `Win32NT` であること。前段の feed / OS 条件が満たされなければ architecture の判定には到達しない。 (`tools/packaging/install.ps1:100-105`)
- installer は `PROCESSOR_ARCHITEW6432` が falsy なら本変数を使う。選ばれた `$arch` が `AMD64` と等しくないと `Die` が stderr に `strata installer: ...` を出して throw し、後続の Windows x86_64 installer 処理へ進まない。 (`tools/packaging/install.ps1:24,104-106`)
- Control の machine 判定は `sysinfo.is_windows()` が真のときだけ本変数を含む Windows 分岐を使う。さらに `PROCESSOR_ARCHITEW6432` が空または空白であることが、本変数が選ばれる条件。未設定や空なら interpreter platform tag に fallback する。 (`terminal/strata_control/sysinfo.py:24-25,55-78`)
- `targets.host_platform()` は `sysinfo.machine()` の結果を小文字化し、`amd64` を `x86_64`、`arm64` を `arm64` に揃えて OS 名と結合する。その target は backend support や component resolution に使われる。対象 CLI で `--target` が指定される場合、その指定値が `host_platform()` の自動判定に優先する。 (`terminal/strata_control/targets.py:33-57`, `terminal/strata_cli/cli.py:2055-2057`)
- agent の環境引き継ぎでは、この名前が `KEEP` allowlist に一致する場合に限って環境値のコピー対象になる。これは値の意味を変える条件判定ではない。 (`app/host/server/agent/harness-runtime.mjs:20-36,75-83`)

## 実行時の詳細

installer はスクリプト実行中、feed と OS の前提条件を通過した後に一度値を読み、`PROCESSOR_ARCHITEW6432` が falsy なら `PROCESSOR_ARCHITECTURE` を選ぶ。その値を変更する CLI 引数はこの箇所にない。非 `AMD64` ならエラー出力後に処理を止め、`AMD64` なら `$platform` を `windows-x86_64` に設定して installer を続ける。 (`tools/packaging/install.ps1:100-116`)

Control の `_windows_machine()` は `sysinfo.machine()` が呼ばれるたびに `os.environ.get()` を実行し、関数内 cache はない。環境値は前後空白除去後に小文字化して既知名の辞書へ照合し、未知値は変換せず返す。`PROCESSOR_ARCHITEW6432` と本変数の両方が空なら `sysconfig.get_platform()` の値から `ARM64`、`AMD64`、または `x86` 等を推定する。例外時は tag を空として `x86` に fallback する。したがって、プロセス内で環境辞書が呼び出し前に変われば次の呼び出しに反映される。 (`terminal/strata_control/sysinfo.py:55-78`)

`targets.host_platform()` は得た machine 名を platform key に変換する。engine/component の対象選択、互換性判定、更新や setup の host 情報などへ伝播するが、値そのものを engine に渡す処理ではない。agent 経路だけは allowlist 済みの元の環境値を Harness 起動環境にコピーする。 (`terminal/strata_control/targets.py:33-57`, `terminal/strata_control/components.py:214`, `terminal/strata_control/engine_component.py:1214`, `terminal/strata_cli/cli.py:2055-2061`, `app/host/server/agent/harness-runtime.mjs:25-36,75-83`)

## ログと測定値

architecture 不一致で installer が停止するときの文言は `this computer ($arch) is a Windows on ARM PC. Strata needs an NVIDIA or AMD graphics card and has no engine for ARM processors, so it could not run a model here. Run this installer on a Windows PC with an Intel or AMD processor (x64) and one of those cards.`。`Die` は stderr に `strata installer: ` を付けて出力し、throw する。選択値が `AMD64` のときは `This computer: Windows $arch ($platform)` を表示する。 (`tools/packaging/install.ps1:24,105,110-112`)

## 根拠

- `tools/packaging/install.ps1:24,100-116` — installer の前提条件、変数選択、比較、失敗・継続経路。
- `terminal/strata_control/sysinfo.py:20-21,55-78` — Windows 値の取得、正規化、fallback、呼び出しごとの評価。
- `terminal/strata_control/targets.py:25-57` — OS / machine から host platform を作り、backend 対応を判定する処理。
- `terminal/strata_control/components.py:214`, `terminal/strata_control/engine_component.py:1214`, `terminal/strata_cli/cli.py:2055-2061` — host target が component 処理へ使われる箇所。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — allowlist による値の引き継ぎ。

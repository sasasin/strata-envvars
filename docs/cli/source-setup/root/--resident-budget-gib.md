# `source-setup --resident-budget-gib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `terminal/setup.py`（`setup.sh`、Windows の setup wrapper から起動される setup） |
| オプション | `--resident-budget-gib` |
| 別名 | なし（setup parser）。エンジンの `strata generate` には別名 `--ram-experts-gb` もあるが、この setup オプションの別名ではない |
| 値 | `N`（GiB、`float`）。setup では `N > 0` が必要 |

## 役割

UD-Q4_K_XL または UD-IQ4_XS の setup で、モデルの expert のうち指定 GiB 分を RAM に常駐させ、残りをモデルファイルから読む実行モードを選びます。setup は値を実行設定の `args` に `--resident-budget-gib N` として保存します。モデル・PC の条件によりこのモードが使われない場合は警告されます。

## 使い方

```sh
# UD-Q4_K_XL の実行設定を 32 GiB の RAM budget で作り、setup 後にモデルを自動起動しない
python3 terminal/setup.py --model UD-Q4_K_XL --resident-budget-gib 32 --no-start
```

これは setup の実行例であり、モデルファイルの取得や実行設定の作成を行います。`--no-start` は setup 完了後のモデル起動を抑止します。

## 値と既定値

- setup parser は `float` として読み取り、値が指定された場合に `> 0` を検証します。0、負数、NaN は setup の引数エラーになります。指定値の上限は setup 側で定めていません。正の無限大は `> 0` 判定を通りますが、budget を整数化する処理で通常の値として扱えず、正常な setup 値として保証されません（`terminal/setup.py:11569-11571, 11639-11640, 4202-4210`）。
- 省略時は、このオプション自身に固定の既定値はありません。対象モデルで RAM budget モードが選ばれると、RAM 容量などから推奨値が算出されます。setup の計算は通常、RAM から OS・engine・残りの expert を読む file cache 用の 17 GB を差し引き、KV cache が RAM にある場合はその分も差し引き、最低 8 GiB・expert 総量以下に丸めます。UMA GPU では別の余白ルールです（`terminal/setup.py:3951-3964`）。
- 明示値が setup の推奨値より大きい場合も拒否せず指定値を保ち、リスクを警告します（`terminal/setup.py:4199-4210`）。

## 実行時の動作

- setup の対象モデル定義には UD-Q4_K_XL と UD-IQ4_XS が `budget: True` として登録されています（`terminal/setup.py:480-494`）。これらのモデルで明示値を渡すと RAM budget モードを選択し、設定生成時に `--resident-budget-gib <値>` をエンジン引数へ追加します（`terminal/setup.py:12074-12079, 12104-12111`; `terminal/strata_control/setup_config.py:333-336`）。
- setup 未指定時も対象モデルが予算モードを必要とすると推奨値を設定します。推奨値を明示値が超える場合は保持する一方、engine は起動時に利用可能な RAM（Windows では commit limit も）と headroom に合わせて値を clamp し、その旨を stderr に出力します（`terminal/setup.py:4202-4210`; `engine/src/core/expert_source.cpp:4044-4066`; `engine/include/strata/core/resident_ram_copy.hpp:53-60`）。
- engine は正の値を byte 数に変換し、`--mmap-experts` と resident CPU expert mode を有効にします。expert profile の順位が高いものから予算内を RAM にコピーし、残りは mapped model files から読みます（`engine/src/program/generate.cpp:4242-4257`; `engine/src/core/expert_source.cpp:4044-4057`）。setup 自体が開始するモデル処理の実行モードの根拠はこの引数転送までであり、ファイル I/O の詳細は engine 実装に基づきます。
- 複数 GPU 指定では engine によって budget 付き layer split を使えない組合せがあり、その場合 setup は1 GPUに切り替えると警告します。`resident_split()` 対応 engine は budget を保った split を許します（`terminal/setup.py:7163-7205`）。
- 64K 以上の context で KV streaming が有効な場合、setup が推奨した budget は KV cache 分を差し引いて調整できます。一方、明示 budget は指定値を保ち、KV cache の RAM はその上乗せになる旨を警告します（`terminal/strata_control/setup_config.py:301-326`）。
- UD-Q4_K_XL / UD-IQ4_XS 以外で指定すると setup は「このモデル向けではない」と警告します。Flash-Next 系の別 family（Qwen3.6 や HY4）では該当設定は使わないという警告経路があります（`terminal/setup.py:12118-12120, 9908-9910, 10328-10329`）。

## 適用条件と副作用

- setup の正の値により対象 Unsloth モデルでは、RAM 常駐量とストレージから読む量が変わります。expert 全体を RAM に置く場合と比べ、残りの expert はモデルファイルから読み出されます（`terminal/setup.py:4083-4087, 12075-12080`; `terminal/strata_control/setup_config.py:333-335`）。
- 対象モデルで明示 budget を使いながら複数 GPU を選んだ場合、対応 engine でなければ1 GPUのみになります（`terminal/setup.py:7163-7170, 7203-7205`）。
- 正の予算を engine が利用可能な RAM 等に合わせて縮める際は stderr に通知されます。利用可能メモリを測れない場合、engine の expert source 初期化はエラーを返します（`engine/src/core/expert_source.cpp:4044-4057, 4049-4052`）。
- setup parser は 0 を拒否しますが、engine の直接引数 `strata generate --resident-budget-gib 0` は受理され、GPU + SSD only を選ぶ別動作です。この engine 直呼びの意味は setup オプションには適用されません（`terminal/setup.py:11639-11640`; `engine/src/program/generate.cpp:4242-4250`）。

## 出力とエラー

- 0 以下などの値は `argparse` の `ap.error` で拒否され、エラーメッセージは「GiB の数値は 0 より大きい値が必要」と案内します（`terminal/setup.py:11639-11640`）。
- 指定値が推奨値を超えると setup は warning を出し、値は保持します。engine 起動時に利用可能量を超えれば、stderr に clamp 後の値を出します（`terminal/setup.py:4205-4209`; `engine/src/core/expert_source.cpp:4057-4066`; `engine/include/strata/core/resident_ram_copy.hpp:53-60`）。
- engine が利用可能メモリを取得できない場合、resident budget の初期化は失敗します（`engine/src/core/expert_source.cpp:4049-4052`）。

## 根拠

- `terminal/setup.py:11569-11571` — setup parser の型、値名、対象モデルの help。
- `terminal/setup.py:11639-11640` — setup 側の正数 validation。
- `terminal/setup.py:3951-3964, 4199-4210` — setup の推奨値と、明示値を保つ条件。
- `terminal/setup.py:12074-12120` — 対象モデルでの budget 選択、利用者向け出力、対象外モデルへの警告。
- `terminal/strata_control/setup_config.py:319-350` — KV streaming との相互作用と、最終 engine 引数への追加。
- `terminal/setup.py:7163-7205` — 複数 GPU と resident split による適用差。
- `engine/src/program/generate.cpp:4242-4257` — engine parser の alias、ゼロ値と正値の分岐、正値時の RAM/mmap 設定。
- `engine/src/core/expert_source.cpp:4044-4066, 4258-4264` — 利用可能メモリによる clamp と expert copy budget の適用。
- `engine/include/strata/core/resident_ram_copy.hpp:53-60` — clamp 時の stderr メッセージ。

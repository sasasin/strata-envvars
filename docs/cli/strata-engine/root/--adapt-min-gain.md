# `--adapt-min-gain`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--adapt-min-gain` |
| 別名 | なし |
| 値 | `F`。`std::atof` で `float` に変換。既定値 `1.5`。明示的な範囲検証なし |

## 役割

`--serve` 中の expert adaptive tier が、VRAM に載せる候補 expert と置き換える resident expert の decayed routing count の差に要求する最小値を指定します。値を大きくすると条件を満たす置換が減ります。設定値を参照するのは serve のブロッキング tier と非同期 tier です。通常の非 serve decode にある別の adaptive 処理は、この引数ではなく `1.5` を直接比較に使います。

## 使い方

```sh
# serve の adaptive tier に必要な routing count の差を 2.0 にする
strata --serve --adapt-min-gain 2.0
```

モデルなど、その実行に必要な他の引数と組み合わせてください。

## 値と既定値

- 省略時は `1.5f` です（`engine/src/program/generate.cpp:1054-1056`）。
- parser は次の引数を `std::atof` で読み `float` に格納します（同 `:4058-4061`）。このオプション固有の下限・上限チェックや補正はありません。数値として解釈できない文字列は `atof` の変換結果（通常 `0`）として扱われ、値を拒否する検証経路はありません。
- 複数回指定すると、引数走査中に代入されるため最後の値が残ります（同 `:3842-3847`, `:4060`）。
- 値を省略すると `next` が標準エラーに `--adapt-min-gain needs a value` を出し、終了コード `2` で終了します（同 `:3844-3846`）。

## 実行時の動作

serve のブロッキング tier は各適応ラウンドで routing count を snapshot し、現在のカウントを `--adapt-decay` の係数で減衰させます（`engine/src/program/generate.cpp:15342-15346`）。expert の routing 回数は layer と expert ごとに加算されます（`engine/src/core/expert_source.cpp:5472-5474`）。候補 expert は未常駐かつ count が `2.0` 以上のものから選ばれ、resident 側の置換対象は pinned でないものから選ばれます。同じ layer 内で候補を多い順、置換対象を少ない順に並べ、候補 count が置換対象 count にこの値を加えた値以上なら置換候補にします。したがって比較は `候補 − 置換対象 >= F` で、等しい場合も通過します（`engine/src/program/generate.cpp:15362-15375`）。採用候補は差の大きい順に並び、1 ラウンドの上限 `--adapt-swaps` に切り詰められます（同 `:15378-15379`）。

非同期 tier の選定処理も同じ設定値で同じ差の比較を行い、差の大きい順に並べてラウンド上限まで選びます（同 `:15632-15659`）。選ばれた expert は VRAM cache と resident 側の間で入れ替えられます。非同期 tier の機能条件は `--serve`、adaptive tier が有効であること、resident RAM mode または expert arena などです。条件に合わない場合は非同期 tier が無効化されブロッキング tierに戻る経路があります（同 `:11774-11812`）。

## 適用条件と副作用

この値は serve の adaptive tier が置換候補を選ぶときにのみ参照されます。通常の非 serve decode にも adaptive refill はありますが、その処理は閾値 `1.5f` を直接使い、このオプション値を参照しません（`engine/src/program/generate.cpp:24735-24748`）。serve でも、adaptive tier 自体が無効（`--adapt-every <= 0` または `--adapt-swaps <= 0`）なら使用されません。routing count の初期化条件は同 `:15001-15002` です。

このオプション自体は設定値を保持するだけで、ファイルやネットワークを直接操作しません。条件を満たした置換は GPU expert cache と resident expert source の内容・resident 表を更新し、evicted expert の prefetch などを行います（同 `:15401-15402`, `:15440-15469`）。専用の環境変数による上書きは parser とこの値の参照箇所では確認できません。

## 出力とエラー

値の範囲検証エラーや値の補正を行うコードは確認できません。値不足では前述の標準エラーと終了コード `2` になります。serve 中に選定後の expert copy が失敗した場合、標準エラーに `strata serve: adaptive swap copy failed ...` を出して処理を失敗させます（`engine/src/program/generate.cpp:15458-15464`）。

## 根拠

- `engine/src/program/generate.cpp:1045-1061` — adaptive 設定の既定値と tier の説明。
- `engine/src/program/generate.cpp:1497-1504` — CLI usage に記載された説明。
- `engine/src/program/generate.cpp:3842-3849, 4058-4061` — 引数取得、既定値を上書きする parser。
- `engine/src/program/generate.cpp:15342-15379, 15632-15659` — serve のブロッキング／非同期 tier における count 減衰、候補選択、閾値適用。
- `engine/src/core/expert_source.cpp:5472-5474` — layer/expert ごとの routing count 加算。
- `engine/src/program/generate.cpp:11774-11812` — 非同期 tier の適用条件と無効化経路。
- `engine/src/program/generate.cpp:24735-24748` — 非 serve 経路の固定 `1.5f` 比較と refill。

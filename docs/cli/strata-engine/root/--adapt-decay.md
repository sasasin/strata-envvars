# `--adapt-decay`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata` |
| オプション | `--adapt-decay` |
| 別名 | なし |
| 値 | 数値引数。`std::atof` で `float` に変換される。ソースに範囲検証はない |

## 役割

適応型 expert cache が参照する routing 使用量を、各適応ラウンドの後にどれだけ残すかを指定します。使用量はレイヤー・expert ごとに保持され、適応型の入れ替え候補と退避候補の順位付けに使われます。係数を小さくすると過去ラウンドの使用量がより強く減衰し、大きくすると残りやすくなります。ソースで確認できる既定値は `0.7` です（`src/program/generate.cpp:695`）。

## 使い方

```sh
strata --adapt-decay 0.7 --adapt-every 4 --adapt-swaps 96 --serve ...
```

`...` はモデル・serve 設定など、この実行に必要な引数に置き換えてください。`--adapt-decay` は値を1つ取ります。

## 値と既定値

- 省略時は `0.7f` です（`src/program/generate.cpp:695`）。
- 指定値は `std::atof` の戻り値を `float` に変換して格納します（`src/program/generate.cpp:2627`）。別名や追加の値検証は parser にありません。
- parser は指定値に上限・下限を設けていません。したがって、通常想定される `0` から `1` の範囲外も、parser 上は拒否されません。変換できない文字列は `atof` の規則により `0` として扱われます。
- 同じオプションを複数回指定した場合は、引数を順に処理して同じフィールドへ代入するため、最後に処理された値が残ります（`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2627`）。
- 値を省いて末尾に置くと `--adapt-decay needs a value` を標準エラーへ出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

適応機能が有効な実行では、`--adapt-every` と `--adapt-swaps` がともに正のとき routing 使用量の配列を初期化します。serve 経路では、さらに全 expert がすでに VRAM にある場合は配列を作らず、適応カウントを行いません（`src/program/generate.cpp:10028-10029`）。通常の非 serve 経路も両設定が正のとき使用量配列を初期化します（`src/program/generate.cpp:16185`）。

適応ラウンドでは、蓄積した使用量から候補を評価して expert の入れ替えを選び、その後、各使用量 `v` に `v *= adapt_decay` を適用します。serve の通常ラウンドと非同期ラウンドの両方、および通常の speculative / 非 serve ラウンドで同じ係数が使われます（`src/program/generate.cpp:10302-10328`, `src/program/generate.cpp:10460`, `src/program/generate.cpp:10735-10745`, `src/program/generate.cpp:16301-16321`, `src/program/generate.cpp:16374-16377`）。候補判定の最低使用量 `2.0` と通常 serve の入れ替え差 `--adapt-min-gain` は別の条件です（同: `src/program/generate.cpp:10313-10324`）。

`--adapt-every` は適応ラウンドの頻度を決め、`--adapt-swaps` は1回のラウンドで選ぶ最大入れ替え数を制限します。`--adapt-decay` は頻度や最大数を変えず、各ラウンド後の使用量だけをスケールします。`--adapt-every` が0以下、または `--adapt-swaps` が0以下なら使用量配列が初期化されず、この係数は適応処理に使われません（同: `src/program/generate.cpp:10028-10029`, `src/program/generate.cpp:16185`）。

`--expert-profile-save` を併用すると、各適応ラウンドで減衰前の使用量を累積 heat に加え、その後に配列を減衰します。そのため、この係数は実行中の順位付けに加え、保存 profile に蓄積される routing 履歴にも影響します（`src/program/generate.cpp:10446-10460`, `src/program/generate.cpp:10742-10745`）。

## 適用条件と副作用

この値は適応型 VRAM expert tier が動く経路で使用されます。全 expert が VRAM にある場合、または `--adapt-every` / `--adapt-swaps` により使用量配列が無効の場合には効果がありません。通常の適応では、入れ替えに伴って resident table が更新され、expert blob の GPU へのコピーや、退避 expert の読み戻し先の prefetch が行われます（`src/program/generate.cpp:10345-10412`, `src/program/generate.cpp:16323-16369`）。

ソースに係数の範囲検証はありません。負値や `1` より大きい値も parser を通過し、減衰ではなく符号反転や増幅につながり得ます。これは受理されることから分かる計算上の帰結であり、そのような値の運用上の安全性・有用性は確認していません。

## 出力とエラー

オプション値そのものに対する範囲エラーや警告は確認できません。値の欠落時は前述の標準エラーと終了コード `2` です。parser には `--adapt-decay` の分岐がありますが、同ファイルの組み込み `usage()` の表示項目（`src/program/generate.cpp:806-1078`）にはこのオプションの説明がありません。適応処理自体で GPU への入れ替えコピーに失敗した場合は、serve 経路で `adaptive swap copy failed`（または batched copy の失敗）を標準エラーに出して処理を失敗させ、通常の speculative 経路では `an adaptive refill failed` を出して失敗します（`src/program/generate.cpp:10400-10405`, `src/program/generate.cpp:10430-10433`, `src/program/generate.cpp:16323-16326`, `src/program/generate.cpp:16347-16369`）。これらはこのオプション固有の validation error ではなく、適応コピーの失敗経路です。

## 根拠

- 既定値と値の意味: `src/program/generate.cpp:695-696`
- parser の変換: `src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2626-2629`
- 使用量配列の有効条件: `src/program/generate.cpp:10028-10029`, `src/program/generate.cpp:16185`
- serve 適応の候補選定と減衰: `src/program/generate.cpp:10302-10328`, `src/program/generate.cpp:10446-10460`
- 非同期 serve の減衰: `src/program/generate.cpp:10735-10745`
- 非 serve / speculative 適応と減衰: `src/program/generate.cpp:16301-16321`, `src/program/generate.cpp:16374-16377`
- 保存 profile の routing 累積: `src/program/generate.cpp:10446-10460`, `src/program/generate.cpp:10742-10745`

調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、表示上の未コミット変更はありませんでした。安全に実行できる同一 revision の生成済み CLI は確認していないため、CLI `--help` は実行していません。parser と一致する補助 help の照合、および Release 配布物での挙動確認は調査範囲外です。

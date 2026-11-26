# `--expert-profile-save-every`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数。`--serve` モード） |
| オプション | `--expert-profile-save-every` |
| 別名 | なし |
| 値 | 分単位の数値（`double`） |

## 役割

`--expert-profile-save` で指定した expert profile の定期保存間隔を分単位で指定します。単独では保存を有効にせず、`--serve` で保存先を指定し、適応型 expert tier と profile 保存に必要な状態がそろった場合に、リクエスト間で学習結果を保存します。

## 使い方

```sh
# エンジンを serve モードで起動し、適応型 tier が有効な構成で profile を 10 分ごとに保存する
engine/strata --serve --pack ./model.strata --expert-profile ./initial-profile.bin \
  --expert-profile-save ./learned-profile.bin --expert-profile-save-every 10
```

実際に保存するには、モデルや tier 設定など `--serve` に必要な引数も指定してください。指定先に既存ファイルがあれば、保存成功時に置き換えます。

## 値と既定値

- 省略時は `10.0` 分です。
- parser は次の引数を `std::atof` で `double` に変換します。専用の範囲検証やエラー処理はありません。複数回指定した場合は、引数解析ループで後の値が前の値を上書きします。
- 値が `0` 以下だと定期保存の条件（値が `0` より大きいこと）を満たしません。その場合も終了時の保存は別に試みます。
- 値の引数を省略すると、parser は stderr に値が必要だと表示して終了コード `2` で終了します。

## 実行時の動作

- 周期判定は `--serve` の入力ループで行われ、直前の保存時刻から指定分数以上経過していて、次の入力行が `QUIT` でなければ、そのリクエストを処理する前に `periodic` 保存を呼び出します。`QUIT` または標準入力の終了時には、ループ後に `exit` 保存を試みます。
- 定期・終了時の保存には `--expert-profile-save <path>` が必要です。保存先が空でなくても、適応型 tier の使用カウントまたは residency 情報がない場合は「nothing will be saved」という警告を stderr に出します。全 expert が resident の経路では通常の `heat` を初期化しないため、通常の保存関数は何も書きません。
- 保存可能な経路では、resident/pending 中の expert と起動後に数えた routing を用いて順位を作り、`--expert-profile-save` のパスへ書き込みます。既存の `--expert-profile` があれば、読み込んだ順位も順位付けに使う prior として保持します。
- 既存ファイルを直接途中書き込みせず、`<保存先>.tmp` に書いた後、rename で保存先へ置き換えます。書き込みに失敗すると一時ファイルを削除して stderr に失敗理由を出します。呼び出し側は保存失敗を終了エラーへ伝播せず、その後の処理を続けます。
- SYCL 実装では、device 側 routing counter がある経路でも周期保存対象となり、保存時に counter を読み取って順位を作ります。通常の CUDA/HIP 側の経路とは、device counter の集計と初期 profile の prior の扱いが異なります。

## 適用条件と副作用

- この間隔が使われるのは `--serve` のみです。`--serve` 以外の parser 経路で値を受理しても、この periodic save loop は実行されません。
- このオプションだけでは保存先を設定しません。保存には `--expert-profile-save` が必要で、実際の保存には適応型 tier の routing count と residency 状態（または SYCL device counter）が必要です。
- 保存先のファイルを作成・置換し、失敗時には `<保存先>.tmp` を削除します。パスの親ディレクトリ作成はこの書き込み処理では行いません。

## 出力とエラー

- 値が不足すると parser が stderr に `--expert-profile-save-every needs a value` を出し、終了コード `2` で終了します。
- 保存可能な状態がない場合は stderr に保存できない旨の警告を出します。成功時は保存先と periodic/exit の理由を stderr に出し、書き込み失敗時は理由を stderr に出します。
- 保存処理自体はエラーを呼び出し元に返さないため、profile の保存失敗だけでこの処理から非ゼロ終了することはありません。

## 根拠

- `engine/src/program/generate.cpp:937` — interval の既定値 `10.0`。
- `engine/src/program/generate.cpp:3842-3847,4215-4216` — argv parser、値の取得と `std::atof` 変換。値不足時の stderr と終了コード。
- `engine/src/program/generate.cpp:1407-1410` — engine help にある serve 用途、終了時・周期保存と `0` の説明（補助資料）。
- `engine/src/program/generate.cpp:15091-15101` — 保存先指定、adaptive usage/residency 条件、警告と heat 初期化。
- `engine/src/program/generate.cpp:15342-15346,15804-15808` — routing usage の累積。
- `engine/src/program/generate.cpp:15955-15973,18503-18507,23958` — profile の順位付けと保存、周期判定、終了時保存。
- `engine/src/core/expert_cache.cpp:246-273,275-315` — resident/heat/prior による順位付け、`.tmp` への書き込み、rename による置換、失敗処理。
- `engine/sycl/src/program/generate.cpp:2177-2178,8761-8773,9345-9393,10285-10289,13283` — SYCL parser、device counter を含む保存経路と periodic/終了時の呼び出し。
- `docs/cli/README.md:1036-1038,1096` — `strata-engine` の root scope と対象リンク。

# `--expert-profile-save-every`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--expert-profile-save-every` |
| 別名 | なし |
| 値 | 分単位の数値（小数も受理）。既定値は `10` 分。 |

## 役割

`--expert-profile-save` で指定した学習済み expert profile を、サーバー稼働中に何分ごとに定期保存するかを指定します。保存判定はアイドル時間中のタイマーではなく、サーバーが次のリクエストを処理する直前に行われます。`0` を指定すると定期保存を無効にし、終了時の保存だけにできます。

## 使い方

```sh
strata --serve --pack ./pack --native ./model.gguf \
  --expert-profile-save ./learned-profile.bin \
  --expert-profile-save-every 30
```

この例は保存間隔を30分にします。保存先など `--expert-profile-save` 自体の条件は [`--expert-profile-save`](--expert-profile-save.md) を参照してください。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。既定値は `10.0` 分です（`src/program/generate.cpp:590-592,2751-2752`）。
- parser に範囲検証や変換エラー検出はありません。たとえば数値として読めない文字列は `atof` の規則で `0` になり、数値の後ろに解釈できない文字がある場合もその先は検証されません（`src/program/generate.cpp:2751-2752`）。
- `0` または負数では、定期保存の条件 `expert_profile_save_min > 0` を満たさないため定期保存されません。小数の正数はその分数相当の間隔として比較されます（`src/program/generate.cpp:12016-12019`）。
- 値を省略すると parser は stderr に `--expert-profile-save-every needs a value` を出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2421,2751-2752`）。

## 実行時の動作

このオプション単独では保存先を設定しません。保存先の `--expert-profile-save` が空なら、routing の集計も保存も行われません。保存先が指定されていても、全 expert が常駐する場合は集計が初期化されません。また、適応型 tier の使用カウントまたは residency table が利用できない場合は stderr に「適応型 tier と `--expert-profile` が必要」と警告し、profile は保存されません（`src/program/generate.cpp:10070-10080`）。

保存可能な構成では routing 使用量を起動後から累積し、保存時点の residency と累積値で expert を順位付けした profile を書きます。既に `--expert-profile` で profile を読み込んだ場合、その順位が同点時の優先順として使われます（`src/program/generate.cpp:4458-4461,10446-10450,10739-10744,10888-10900`）。

定期保存の時計は集計状態の初期化時に開始します。間隔を過ぎた場合、次のリクエストを処理する前に1回保存します。リクエストが来なければ、間隔を過ぎてもその時点では保存されません。`QUIT` はこの定期保存判定を飛ばし、ループ終了後の保存処理に進みます。標準入力の終了でサーバーがループを抜ける経路も同じ終了時保存を通ります（`src/program/generate.cpp:10080,12016-12020,15685`）。

## 適用条件と副作用

- 保存機能は `--serve` の適応型 tier を対象とします。間隔を指定しても `--expert-profile-save` がなければ効果はありません（`src/program/generate.cpp:990-993,10070-10078`）。
- profile は保存先と同じ名前に直接書くのではなく、`<保存先>.tmp` に一時書き込みしてから rename します。rename は既存ファイルを置き換えます。作成・書き込み・rename に失敗した場合、一時ファイルを削除し保存失敗を報告します（`src/core/expert_cache.cpp:172-211`）。
- 保存成功時は stderr に保存先と理由（`periodic` または終了時の `exit`）が出ます。保存失敗時も stderr にエラーが出ますが、この helper は失敗でサーバーを終了させません。失敗の有無にかかわらず次の間隔の基準時刻を更新するため、失敗後は次の間隔が経過してから再試行されます（`src/program/generate.cpp:10888-10905`）。

## 出力とエラー

無効な数値文字列を拒否する parser validation はありません。値欠落時は stderr にエラーを出して終了コード `2`、未知の引数は stderr に `unknown argument` と usage を出して終了コード `2` です（`src/program/generate.cpp:2418-2421,2787-2792`）。

適応型 tier など保存要件が満たされない場合は警告が stderr に出て、保存は行われません。profile の書き込み失敗は stderr に理由を出しますが、保存処理だけの失敗は致命エラーとして扱われません（`src/program/generate.cpp:10073-10078,10900-10905`）。

## 根拠

- `src/program/generate.cpp:590-592,990-993,2750-2752` — option の既定値、help 説明、parser。
- `src/program/generate.cpp:10070-10080,10446-10450,10739-10744` — 保存要件と routing 使用量の集計。
- `src/program/generate.cpp:10888-10905,12016-12020,15685` — profile の書き込み、定期保存判定、終了時保存。
- `src/core/expert_cache.cpp:143-169,172-211` — residency・routing・既存順位による順位付けと、一時ファイルからの置換。
- `serve/server.py:3197-3217` — Terminal の server 設定からエンジン引数へ渡す経路。設定キーが `expert_profile_save_every` として数値かつ非負の場合にこのオプションを付加します。

調査範囲は上記 checkout のソースです。同一 revision のビルド済み CLI help や Release 配布物は確認していません。help 表示は `src/program/generate.cpp` の usage 文字列を補助根拠として参照しました。

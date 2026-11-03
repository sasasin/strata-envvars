# `STRATA_DF2_DUMP_ROUND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal エンジンの DFlash2 drafter が `STRATA_DF2_DUMP` で指定されたファイルへ診断ダンプを書き出す round を選びます。単独では動作せず、ダンプ先の `STRATA_DF2_DUMP` が設定され、DFlash2 の pack が Metal `Window` に bind されている経路でのみ読み取られます。通常の推論設定ではなく、診断・照合用の出力タイミング指定です。

## 値と判定

読み取り時に `std::atoi` を使い、整数への変換結果を round カウンタとの完全一致に使います。文字列全体の妥当性検査、clamp、範囲チェックはありません。

| 状態 | 判定と結果 |
|---|---|
| `STRATA_DF2_DUMP` が未設定 | `STRATA_DF2_DUMP_ROUND` は読まれません。既定値 3 のままですが、ダンプ先が空なので出力は行われません。 |
| `STRATA_DF2_DUMP` が設定済み、round 変数が未設定 | 既定値 3 を使います。 |
| `STRATA_DF2_DUMP` が設定済み、round 変数が設定済み | `atoi` の結果を使います。空文字や数値に変換できない文字列は 0 になります。先頭の数値部分の後ろに文字があっても、その数値部分が変換されます（例: `3x` は 3）。負値もそのまま保持されます。 |
| `STRATA_DF2_DUMP` が空文字 | 空のパスが保存されるため、round 変数を読み取っても `dump_path.empty()` の判定により行収集・書き出しは行われません。 |

round カウンタは 0 から始まり、各ドラフト実行後に増えます。したがって既定値 3 は、カウンタが 3 のドラフト結果（0 始まりで4回目）を指定します。負値は通常の 0 始まりカウンタと一致しないため書き出し条件に到達しません。

根拠: `metal/src/engine/dflash2.inc:115-121,405,794-795`。

## 有効になる条件

- Metal エンジンの DFlash2 経路であること。CUDA/HIP 側の同名環境変数読み取りは確認できません。
- DFlash2 pack が開かれ、Window が bind されること。環境変数は bind 時に評価されます。DFlash2 が起動しない、または bind 前に失敗する経路では読み取られません。
- `STRATA_DF2_DUMP` が設定され、かつその値が空でないこと。別の CLI 引数や設定値による round 上書きはこのコードにはありません。

`df2_bind()` は既に bound なら早期 return し、設定値は `Df2` インスタンスの `dump_round` に保持されます。したがって bind 後にプロセス環境を変更しても、そのインスタンスでは再評価されません。

根拠: `metal/src/engine/dflash2.inc:282-287,405,409`; Metal の DFlash2 bind 経路は `metal/src/engine/dflash2.inc:1057-1064,1072-1080`。

## 実行時の詳細

`dump_path` が空でない間、DFlash2 に渡された context tap rows と各 draft の tap rows を蓄積します。ドラフト計算後、現在の `d.rounds` が `dump_round` と一致したときに、蓄積状態を検査して指定ファイルを `wb` で開き、ヘッダー、context rows、anchor embedding、その他の診断バッファを書きます。書き出し処理後は `dump_path` を空にして一度きりにします。

観測できる結果は stderr のログです。連続した位置 `0..s` の context rows が揃わない場合は `strata metal: STRATA_DF2_DUMP: the context rows are not 0..%lld, nothing written`、ファイルを開けない場合は `strata metal: cannot write %s` を出します。成功時は書いた context row 数、round 数、パスを `strata metal: STRATA_DF2_DUMP: ... written to ...` の形式で出します。これらの失敗はこの関数内でエラー値を返さず、round 到達後にダンプ先をクリアするため、同じインスタンスでの自動再試行はありません。

根拠: `metal/src/engine/dflash2.inc:683-717,719-738,740-797`。

## 根拠と調査範囲

候補名の全参照を Strata checkout 全体で検索しました。実際の環境読み取りは `metal/src/engine/dflash2.inc:405` の一箇所で、同じファイルの `Df2::dump_round` 初期値は 3 です（`metal/src/engine/dflash2.inc:115-121`）。`tools/dflash2/check_metal_dump.py` には変数の説明コメントがありますが、Python 側で環境値を読む箇所ではありません。

`docs/envvars/000_envvers.md:1007` の候補名は Strata 所有コードの実読み取りで裏付けられました。調査対象 SHA と調査日を冒頭に記載しています。

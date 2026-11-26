# `STRATA_VERIFY_ASYNC_LAUNCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

対応する verifier build で verify window の graph launch を呼び出し側スレッドではなく helper thread に渡すスイッチです。helper thread が launch 中も呼び出し側は CPU doorbell を処理できます。`HostGraphLaunch` は同じ graph を起動し、launch の実エラーを verifier に返します（`engine/src/core/verify.cpp:3895-3927`、`engine/include/strata/core/host_graph_launch.hpp:11-29,42-52`）。

この名前を読む CLI 引数や設定ファイル経路はありません。手動設定した環境値が優先され、該当する Windows HIP defaults は値が未設定の場合だけ補います（`engine/src/core/verify.cpp:3897-3900`、`engine/src/core/arch_defaults.cpp:445-448`）。

この分岐がコンパイルされるのは、HIP 以外の build（ただし `STRATA_HIP_GFX906` 定義時を除く）と、Windows の HIP build（同じく gfx906 を除く）です（`engine/src/core/verify.cpp:1-6`）。したがって CUDA では環境変数を手動設定して使え、Windows HIP でも使えます。gfx906 HIP と Linux HIP にはこの `HostGraphLaunch` 分岐がありません。

未設定時に Strata が自動で `1` を設定するのは、Windows HIP の AMD GPU defaults 経路です。Windows の discrete RDNA3（gfx1100/1101/1102、`integrated == false`）では gfx11 exact defaults が有効な場合に、Windows gfx1151 では gfx1151 defaults が有効な場合に対象になります。いずれも既に環境変数が存在すれば値を保ちます。gfx1151 では `STRATA_GFX1151_DEFAULTS` の先頭が `0` なら自動設定されません。gfx1100/1101/1102 では `STRATA_GFX11_DEFAULTS` の先頭が `0`、または `STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のとき gfx11 defaults 自体が適用されません（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:293-299,312-324,444-452`、`engine/include/strata/core/gfx11_extra.hpp:27-45,74-79`、`engine/include/strata/core/defaults_026.hpp:21-29`）。

## 値と判定

`verify.cpp` は `std::getenv` の返り値が非 null で、かつ値の先頭 1 文字が ASCII の `1` なら有効とします。文字列全体の比較や数値変換はしません（`engine/src/core/verify.cpp:3897-3900`）。

| 条件 | unset | helper launch になる値 | helper launch にならない値 |
|---|---|---|---|
| 対応 build で自動 defaults の条件外、または defaults が無効 | 無効 | `1`、`10`、`1anything` | 空文字、`0`、`0anything`、`2`、`true`、`TRUE`、` 1`、`01` |
| Windows HIP の対象 defaults が有効で、変数が unset | 起動時に `1` を設定して有効 | 自動設定された `1` | 該当なし |
| Windows HIP の対象 defaults が有効で、変数が空文字を含め設定済み | 設定値を保持 | 先頭文字が `1` の値 | 空文字、先頭文字が `1` 以外の値 |

大文字小文字、空白、後続文字の妥当性は検査しません。特に空文字は「設定済み」として自動 default による上書きを防ぎますが、読み取り側では無効です（`engine/src/core/arch_defaults.cpp:445-448`、`engine/src/core/verify.cpp:3897-3900`）。

## 有効になる条件

- ビルドが `STRATA_VERIFY_HGL` 分岐を含むこと（CUDA build、または Windows HIP build。gfx906 HIP は除外）（`engine/src/core/verify.cpp:2-6,3895`）。
- verifier が `!pre` の verify window launch に進むこと。そこで対象 graph launch の呼び出しに値が使われます（`engine/src/core/verify.cpp:3884-3899,3926-3927`）。
- 環境変数の先頭文字が `1` であること。Windows HIP の自動 default では、gfx1151 は `STRATA_GFX1151_DEFAULTS` が先頭 `0` でないこと、discrete gfx1100/1101/1102 は `STRATA_GFX11_DEFAULTS` が先頭 `0` でなく `STRATA_DEFAULTS` が 0.2.6 token でないことも必要です（`engine/src/core/arch_defaults.cpp:293-299,318-323`、`engine/include/strata/core/gfx11_extra.hpp:27-45`、`engine/include/strata/core/defaults_026.hpp:21-29`）。
- CUDA build ではこのコードによる自動設定はありません。Windows HIP でも上記 GPU/defaults 条件を満たさなければ未設定のままです。これらの場合は、利用者がプロセス起動前に値を設定すれば、対応 build で読み取り対象になります（自動設定箇所: `engine/src/program/generate.cpp:4287-4320`）。

## 実行時の詳細

判定結果は `verify.cpp` 内の関数ローカル `static const bool` に初回評価時に保存されます。初回の非 pre verify window より前に環境変数を設定・変更した値が読まれ、その後の同一プロセス内の変更は反映されません（`engine/src/core/verify.cpp:3884-3900`）。Windows HIP defaults は generate のデバイス情報取得後に適用され、現在のエンジンプロセスの環境へ値を設定します。設定済みの値を上書きしません（`engine/src/program/generate.cpp:4287-4320`、`engine/src/core/arch_defaults.cpp:218-224,445-448`）。

有効時、`HostGraphLaunch` の worker は対象 device を選んでから graph を launch し、呼び出し側は launch 完了を待つ間に doorbell を処理できます。無効時は同じ graph launch を呼び出し側スレッドから行います。有効時も graph 自体は同じで、launch 結果は `query()` / `finish()` 経由で確認されます（`engine/include/strata/core/host_graph_launch.hpp:17-29,42-52`、`engine/src/core/verify.cpp:3926-3944,4018-4028,4156-4166`）。

## ログと測定値

Windows HIP の gfx1151 defaults がこの変数を新たに設定した場合、stderr に次の行を出します。変数が既に存在した場合、この専用行は出ません（`engine/src/core/arch_defaults.cpp:445-452`）。

```text
strata: gfx1151 (Strix Halo): the verify window's graph is launched from a helper thread (the main thread serves the doorbells meanwhile; STRATA_GFX1151_DEFAULTS=0 or STRATA_VERIFY_ASYNC_LAUNCH=0 turns it off)
```

Windows HIP の gfx1100/1101/1102 では gfx11 exact defaults の起動行に `VERIFY_ASYNC_LAUNCH` が含まれます（`engine/src/core/arch_defaults.cpp:318-332`）。明示設定だけの場合、この変数専用の有効化ログはありません。`STRATA_LAUNCH_PROBE` を別途有効にすると、最初の最大 12 window について helper thread 使用表示、launch の状態、doorbell の観測を stderr に出します（`engine/src/core/verify.cpp:3879-3883,3902-3934`）。

launch error は verifier のエラー文字列 `verify: launch: <CUDA error text>` となって失敗を返します。layer が到達しない場合は `verify: layer <番号> never rang (...)`、既存 verifier timeout に達した場合は `verify: timed out at layer <番号>` を返す経路があります（`engine/src/core/verify.cpp:3940-3942,4018-4028,4046-4061,4156-4166`）。ソース資料にこの環境変数による性能測定値は確認できません。

`docs/DETAILS.md:1270` は CUDA の single-request verifier として記載していますが、現行コードは Windows HIP build にも同じ読み取り分岐を持ち、上記の Windows AMD defaults から値を設定します。ここでは現行コードの適用範囲を記載しました。

## 根拠

- `engine/src/core/verify.cpp:1-6,3884-3901,3926-3944,4018-4061,4156-4166`
- `engine/include/strata/core/host_graph_launch.hpp:11-29,35-52`
- `engine/src/program/generate.cpp:4287-4320`
- `engine/src/core/arch_defaults.cpp:218-224,293-299,312-332,444-452`
- `engine/include/strata/core/gfx11_extra.hpp:27-45,74-79`
- `engine/include/strata/core/defaults_026.hpp:21-29`
- `engine/include/strata/kernels/gfx_arch.hpp:15-25,38-39`

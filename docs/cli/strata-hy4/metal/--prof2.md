# `strata-hy4-metal --prof2`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（HY4 Metal runner） |
| オプション | `--prof2` |
| 別名 | なし |
| 値 | なし（フラグ） |

## 役割

Metal runner の GPU profiling を有効にし、通常の `--prof` が集計する層の処理区間に加えて、attention や MoE 内の複数の小区間も別々に計測します。各区間の GPU 実行時間は prefill と decode の profiling レポートとして標準エラーに出ます。性能を変更する設定ではなく、処理を分割して計測する診断用フラグです。

## 使い方

```sh
# プロンプトを prefill し、細分化した GPU 区間時間を表示する
strata-hy4-metal --model model.strata --tokens prompt.ids --prof2

# prefill に続く decode も実行し、両方の profiling レポートを表示する
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --prof2
```

## 値と既定値

`--prof2` は値を取らないフラグです。指定時に `prof` と `prof2` の両方を `true` にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1521-1522`）。未指定時は両方とも `false` です（同:1490）。数値範囲や値の validation はありません。複数回指定しても同じ真偽値を設定するだけです（同:1504-1522）。

## 実行時の動作

parser の `prof` / `prof2` は Runner に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1725-1727`）。`forward_chunk` は `prof || seg_force` を segmented mode とし、`--prof2` 単独でもその mode になります（同:1291-1296）。通常の区間境界では dispatch を実行して結果をラベル別に蓄積し（同:446-455）、`--prof2` が有効なときは `op(label)` の箇所でも追加で区切ります（同:456）。たとえば attention の projection・attention・value/output、MLP の router・experts・shared 部分に個別ラベルがあります（同:1005-1006、1026-1027、1084-1087、1103-1104、1167-1168、1224-1245）。

レポートは蓄積値を区間名の降順時間で並べ、GPU 時間の合計をステップ数で割った ms/step と呼び出し回数を標準エラーに出します（同:1371-1382）。prefill のレポートは処理後に出力され、`--gen` で decode を行った場合は decode レポートも出ます（同:1814-1817、1968-1974）。

## 適用条件と副作用

- profiling は通常の offline prefill/decode 経路に適用されます。`--load-only` では Runner を作る前に終了し（同:1635）、`--serve` では serve 経路へ移って Runner の offline profiling 設定を渡さないため、このオプションの区間レポートは対象外です（同:1636-1675、1715-1727）。
- `--prof` も `prof` を有効にしますが、`prof2` が false のため `op(label)` の細分化境界は追加されません。`--prof2` は `--prof` の基本レポートも有効にします（同:1521-1522、456）。`--seg` は別途 `seg_force` を有効にするフラグですが、`--prof2` はすでに segmented mode を有効にします（同:1523-1524、1295-1296）。
- `--prof3` は別の計測経路です。decode の特定ステップで各 dispatch を単独実行する profiling を行い、`--prof2` の区間集計とは異なります（同:1351-1366、1961-1964）。
- segmented mode では区間ごとに `run_graph` を呼び、通常まとめて実行する dispatch を区間単位に分けます（同:447-455）。計測時の区間実行・分割が行われますが、ここでは性能上の効果は評価していません。

## 出力とエラー

区間時間レポートは `fprintf(stderr, ...)` で出力されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1371-1382`）。`--prof2` 自体に専用の validation error や終了コード分岐は見当たりません。通常のモデル読み込み・初期化・forward の失敗では、それぞれ既存のエラー経路で終了し profiling のレポートまで到達しない場合があります（同:1620-1626、1762-1764、1794-1796）。

decode が `--gen` の指定後すぐ EOS で止まるなど、decode の計測ステップ数が 0 の場合も `report("decode", times.size())` は呼び出されます（同:1951-1955、1968-1971）。レポート内ではステップ数で除算するため、このケースの表示値は有効な ms/step にならない可能性があります（同:1375-1381）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1522` — フラグの初期値と parser 登録。値なしで `prof` と `prof2` を有効化。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:446-456、1291-1296` — 区間計測・集計の仕組みと segmented mode の適用条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:980-1246` — `--prof2` が追加する処理区間の計測ポイント。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1371-1382、1814-1817、1968-1974` — レポート形式、標準エラー出力、prefill/decode の出力位置。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675、1725-1727` — load-only / serve 分岐と Runner 設定の適用範囲。

調査ではソースコードのみを根拠にしました。同一 revision の既存 CLI `--help` は実行していません。GPU 上での時間計測や profiling 値の妥当性は確認していません。
